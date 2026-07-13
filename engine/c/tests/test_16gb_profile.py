"""Issue #119 (epica #116): container v2 (dtype misto por-tensor) e o gate duro de RSS.

Estes testes exercitam o BINARIO C real (`./glm`) contra a fixture sintetica do oraculo
(`tools/make_glm_oracle.py`, pesos aleatorios, arquitetura real glm_moe_dsa em escala
minuscula) -- NAO o checkpoint GLM-5.2 real (~370 GB, indisponivel neste ambiente) e NAO
uma maquina real de 16 GB (issue #118, bloqueada por hardware). O gate de RSS e' logica de
projecao: pode ser provado correto com QUALQUER tamanho de modelo, testando que o processo
aborta de forma limpa quando a projecao (honesta, calculada a partir do modelo carregado)
excede um teto configurado -- nao depende da escala real do GLM-5.2 nem de hardware de 16GB.

Se torch/transformers nao estiverem instalados, ou o motor nao builda neste ambiente, os
testes sao pulados com uma razao explicita (nao skipados silenciosamente).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE_DIR = HERE.parent
GLM_BIN = ENGINE_DIR / "glm"
ORACLE_SCRIPT = ENGINE_DIR / "tools" / "make_glm_oracle.py"
CONVERT_SCRIPT = ENGINE_DIR / "tools" / "convert_fp8_to_int4.py"
GLM_TINY = ENGINE_DIR / "glm_tiny"

sys.path.insert(0, str(ENGINE_DIR / "tools"))


def _have_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


HAVE_ML_STACK = _have_module("torch") and _have_module("transformers") and _have_module("safetensors")


def _build_engine():
    if GLM_BIN.is_file():
        return True
    result = subprocess.run(["make", "glm"], cwd=ENGINE_DIR, capture_output=True, text=True)
    return result.returncode == 0 and GLM_BIN.is_file()


def _ensure_oracle_fixture():
    if (GLM_TINY / "config.json").is_file() and (GLM_TINY / "model.safetensors").is_file():
        return True
    result = subprocess.run([sys.executable, str(ORACLE_SCRIPT)], cwd=ENGINE_DIR,
                            capture_output=True, text=True, timeout=180)
    return result.returncode == 0 and (GLM_TINY / "model.safetensors").is_file()


@unittest.skipUnless(HAVE_ML_STACK, "torch/transformers/safetensors indisponiveis: fixture "
                     "sintetica nao pode ser gerada. Rode 'pip install torch transformers "
                     "safetensors' para exercitar estes testes localmente (nao requer o "
                     "checkpoint GLM-5.2 real nem hardware de 16GB).")
class ContainerV2AndRssGateTest(unittest.TestCase):
    """Baseado na fixture do oraculo (make_glm_oracle.py): arquitetura glm_moe_dsa real,
    pesos aleatorios, minuscula. Nao e' um modelo de linguagem util -- serve so' para
    exercitar o loader/conversor/gate do motor C ponta a ponta."""

    @classmethod
    def setUpClass(cls):
        if not _build_engine():
            raise unittest.SkipTest("nao foi possivel compilar engine/c/glm (make glm falhou)")
        if not _ensure_oracle_fixture():
            raise unittest.SkipTest("nao foi possivel gerar engine/c/glm_tiny (make_glm_oracle.py falhou)")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _run_glm(self, snap, extra_env=None, cap=64, ebits=4, dbits=4, tf=True, timeout=60):
        env = dict(os.environ, SNAP=str(snap))
        if tf:
            env["TF"] = "1"
        if extra_env:
            env.update(extra_env)
        return subprocess.run([str(GLM_BIN), str(cap), str(ebits), str(dbits)],
                              cwd=ENGINE_DIR, env=env, capture_output=True, text=True, timeout=timeout)

    # ---------- container v2: dtype misto por-tensor ----------

    def test_v1_container_has_no_manifest_and_loads_unchanged(self):
        """Container v1 (sem --dtype-map): nenhum container_manifest.json e' escrito, e o
        motor carrega exatamente como antes (nenhuma regressao de comportamento)."""
        outdir = Path(self.tmp.name) / "v1"
        result = subprocess.run([sys.executable, str(CONVERT_SCRIPT), "--indir", str(GLM_TINY),
                                 "--outdir", str(outdir), "--ebits", "4", "--io-bits", "8"],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((outdir / "container_manifest.json").exists())

        run = self._run_glm(outdir, ebits=4, dbits=4)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("CONTAINER v2", run.stderr)

    def test_v2_mixed_dtype_manifest_round_trips_bit_identical(self):
        """Container v2 (--dtype-map): tensores individuais em bits diferentes dos demais da
        mesma categoria. O loader deve ler o manifesto, VALIDAR sem abortar, e os bytes
        empacotados no disco devem ser byte-identicos ao quant aplicado diretamente."""
        import numpy as np
        from safetensors import safe_open
        from safetensors.numpy import load_file

        from convert_fp8_to_int4 import quant_int2, quant_int4

        dtype_map_path = Path(self.tmp.name) / "dtype_map.json"
        overridden_tensor = "model.layers.0.self_attn.q_a_proj.weight"
        dtype_map_path.write_text(json.dumps({re_escape(overridden_tensor): 2}))

        outdir = Path(self.tmp.name) / "v2"
        result = subprocess.run([sys.executable, str(CONVERT_SCRIPT), "--indir", str(GLM_TINY),
                                 "--outdir", str(outdir), "--ebits", "4", "--io-bits", "8",
                                 "--dtype-map", str(dtype_map_path)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)

        manifest = json.loads((outdir / "container_manifest.json").read_text())
        self.assertEqual(manifest["container_version"], 2)
        self.assertEqual(manifest["tensors"][overridden_tensor]["bits"], 2)
        other_tensor = "model.layers.0.self_attn.o_proj.weight"
        self.assertEqual(manifest["tensors"][other_tensor]["bits"], 4)  # default ebits, nao sobrescrito

        with safe_open(GLM_TINY / "model.safetensors", framework="numpy") as f:
            w_override = f.get_tensor(overridden_tensor).astype(np.float32)
            w_default = f.get_tensor(other_tensor).astype(np.float32)
        expected_q, expected_s = quant_int2(w_override, 2)
        expected_q4, expected_s4 = quant_int4(w_default, 4)

        shard = next(outdir.glob("out-*.safetensors"))
        produced = load_file(str(shard))
        np.testing.assert_array_equal(produced[overridden_tensor], expected_q)
        np.testing.assert_array_equal(produced[overridden_tensor + ".qs"], expected_s)
        np.testing.assert_array_equal(produced[other_tensor], expected_q4)
        np.testing.assert_array_equal(produced[other_tensor + ".qs"], expected_s4)

        run = self._run_glm(outdir, ebits=4, dbits=4)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("[CONTAINER v2] manifesto carregado", run.stderr)

    def test_v2_corrupted_manifest_aborts_cleanly_without_crash(self):
        """Manifesto v2 que MENTE sobre o bit-width real de um tensor -> o loader deve
        detectar a inconsistencia e abortar de forma limpa (exit code positivo, sem
        segfault/signal negativo), nunca ler os bytes errados silenciosamente."""
        dtype_map_path = Path(self.tmp.name) / "dtype_map.json"
        overridden_tensor = "model.layers.0.self_attn.q_a_proj.weight"
        dtype_map_path.write_text(json.dumps({re_escape(overridden_tensor): 2}))
        outdir = Path(self.tmp.name) / "v2corrupt"
        subprocess.run([sys.executable, str(CONVERT_SCRIPT), "--indir", str(GLM_TINY),
                        "--outdir", str(outdir), "--ebits", "4", "--io-bits", "8",
                        "--dtype-map", str(dtype_map_path)],
                       capture_output=True, text=True, timeout=60, check=True)
        manifest_path = outdir / "container_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["tensors"][overridden_tensor]["bits"] = 8   # mentira: no disco esta' em int2
        manifest_path.write_text(json.dumps(manifest))

        run = self._run_glm(outdir, ebits=4, dbits=4)
        self.assertGreater(run.returncode, 0)          # abort limpo (exit code positivo)
        self.assertGreaterEqual(run.returncode, 0)      # nunca um signal (returncode negativo = crash)
        self.assertIn("[CONTAINER v2] ABORT", run.stderr)

    # ---------- gate duro de RSS ----------

    def test_rss_gate_disabled_by_default(self):
        """Sem COLI_RSS_CEILING_GB (nem --profile 16gb), o gate fica desligado: comportamento
        idêntico ao motor antes desta issue."""
        run = self._run_glm(GLM_TINY, ebits=16, dbits=16)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("RSS GATE", run.stderr)

    def test_rss_gate_aborts_cleanly_when_projection_exceeds_ceiling(self):
        """Teto microscopico de proposito -> a projecao de pico (mesmo minima, cap=1) SEMPRE
        excede. Prova o requisito da issue: abort limpo (sem crash, sem esperar o OOM-killer
        do kernel), com mensagem acionavel -- sem precisar de hardware real de 16GB."""
        run = self._run_glm(GLM_TINY, extra_env={"COLI_RSS_CEILING_GB": "0.000001"}, ebits=16, dbits=16)
        self.assertEqual(run.returncode, 3)
        self.assertGreaterEqual(run.returncode, 0)      # exit code, nao um signal
        self.assertIn("[RSS GATE] ABORT", run.stderr)
        self.assertIn("docs/profiles/16gb.md", run.stderr)

    def test_rss_gate_does_not_abort_with_generous_ceiling(self):
        run = self._run_glm(GLM_TINY, extra_env={"COLI_RSS_CEILING_GB": "1000"}, ebits=16, dbits=16)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("RSS GATE", run.stderr)

    # ---------- perfil 16gb ----------

    def test_profile_16gb_applies_documented_defaults(self):
        """COLI_PROFILE=16gb aplica os defaults documentados em docs/profiles/16gb.md sem que
        o usuario precise setar cada variavel manualmente."""
        run = self._run_glm(GLM_TINY, extra_env={"COLI_PROFILE": "16gb"}, ebits=16, dbits=16)
        self.assertIn("[PROFILE 16gb]", run.stderr)
        self.assertIn("MTP=0", run.stderr)
        self.assertIn("DSA=1", run.stderr)
        self.assertIn("teto_RSS=13GB", run.stderr)
        # fixture sintetica e' muito menor que o GLM-5.2 real: o teto de 13GB do perfil real
        # NAO deve abortar aqui, so' prova que o perfil aplica e o gate roda com o teto certo.
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertNotIn("RSS GATE", run.stderr)

    def test_profile_16gb_respects_explicit_override(self):
        """Flags explicitas do usuario tem prioridade sobre os defaults do perfil."""
        run = self._run_glm(GLM_TINY, extra_env={"COLI_PROFILE": "16gb", "MTP": "1"}, ebits=16, dbits=16)
        self.assertIn("MTP=1", run.stderr)


def re_escape(name):
    import re
    return re.escape(name)


if __name__ == "__main__":
    unittest.main()
