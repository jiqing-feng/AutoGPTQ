from logging import getLogger
from typing import Optional

import torch
from packaging.version import parse as parse_version


try:
    import triton  # noqa: F401

    TRITON_AVAILABLE = True
except ImportError:
    TRITON_AVAILABLE = False

try:
    import autogptq_cuda_64  # noqa: F401

    AUTOGPTQ_CUDA_AVAILABLE = True
except Exception:
    AUTOGPTQ_CUDA_AVAILABLE = False


try:
    import exllama_kernels  # noqa: F401

    EXLLAMA_KERNELS_AVAILABLE = True
except Exception:
    EXLLAMA_KERNELS_AVAILABLE = False

try:
    import exllamav2_kernels  # noqa: F401

    EXLLAMAV2_KERNELS_AVAILABLE = True
except Exception:
    EXLLAMAV2_KERNELS_AVAILABLE = False

try:
    import cQIGen  # noqa: F401

    QIGEN_AVAILABLE = True
    QIGEN_EXCEPTION = None
except Exception as e:
    QIGEN_AVAILABLE = False
    QIGEN_EXCEPTION = e

try:
    import autogptq_marlin_cuda  # noqa: F401

    MARLIN_AVAILABLE = True
    MARLIN_EXCEPTION = None
except Exception as e:
    MARLIN_AVAILABLE = False
    MARLIN_EXCEPTION = e

try:
    import intel_extension_for_pytorch   # noqa: F401

    IPEX_AVAILABLE = True
    IPEX_EXCEPTION = None
    _warned = False
except Exception as e:
    IPEX_AVAILABLE = False
    IPEX_EXCEPTION = e


logger = getLogger(__name__)


def dynamically_import_QuantLinear(
    use_triton: bool,
    desc_act: bool,
    group_size: int,
    bits: int,
    disable_exllama: Optional[bool] = None,
    disable_exllamav2: bool = False,
    use_qigen: bool = False,
    use_marlin: bool = False,
    use_tritonv2: bool = False,
    use_ipex: bool = False,
):
    try:
        import habana_frameworks.torch.hpu  # noqa: F401
    except Exception as e:
        pass
    else:
        from ..nn_modules.qlinear.qlinear_hpu import QuantLinear
        return QuantLinear

    if not torch.cuda.is_available() and not use_ipex:
        global _warned
        if not _warned:
            logger.warning("No cuda found, set use_ipex=True to use cpu")
            _warned = True
        use_ipex = True
    if use_qigen:
        if not QIGEN_AVAILABLE:
            raise ValueError(
                f"QIGen appears to be not available with the error: {QIGEN_EXCEPTION}. Please check your installation or use `use_qigen=False`."
            )
        from ..nn_modules.qlinear.qlinear_qigen import QuantLinear
    else:
        if use_triton or use_tritonv2:
            if torch.version.hip:
                logger.warning(
                    "Running GPTQ triton version on AMD GPUs is untested and may result in errors or wrong predictions. Please use use_triton=False."
                )
            if use_tritonv2:
                logger.debug("Using tritonv2 for GPTQ")
                from ..nn_modules.qlinear.qlinear_tritonv2 import QuantLinear
            else:
                from ..nn_modules.qlinear.qlinear_triton import QuantLinear
        elif use_ipex:
            assert bits == 4, "IPEX only support 4bit GPTQ"
            if not IPEX_AVAILABLE:
                raise ValueError(
                    f"IPEX appears to be not available with the error: {IPEX_EXCEPTION}. Please install with `pip install intel-extension-for-pytorch`."
                )
            from ..nn_modules.qlinear.qlinear_ipex import QuantLinear
        else:
            # If disable_exllamav2 is True, we want to fall back on the exllama kernel and not the cuda/cuda_old ones.
            if disable_exllama is None:
                if disable_exllamav2:
                    disable_exllama = False
                else:
                    disable_exllama = True
            if bits == 4 and use_marlin:
                from ..nn_modules.qlinear.qlinear_marlin import QuantLinear
            elif bits == 4 and not disable_exllamav2 and EXLLAMAV2_KERNELS_AVAILABLE:
                from ..nn_modules.qlinear.qlinear_exllamav2 import QuantLinear
            elif bits == 4 and not disable_exllama and EXLLAMA_KERNELS_AVAILABLE:
                from ..nn_modules.qlinear.qlinear_exllama import QuantLinear
            elif not desc_act or group_size == -1:
                from ..nn_modules.qlinear.qlinear_cuda_old import QuantLinear
            else:
                from ..nn_modules.qlinear.qlinear_cuda import QuantLinear

    return QuantLinear


def compare_transformers_version(version: str = "v4.28.0", op: str = "eq"):
    assert op in ["eq", "lt", "le", "gt", "ge"]

    from transformers import __version__

    return getattr(parse_version(__version__), f"__{op}__")(parse_version(version))


def compare_pytorch_version(version: str = "v2.0.0", op: str = "eq"):
    assert op in ["eq", "lt", "le", "gt", "ge"]

    from torch import __version__

    return getattr(parse_version(__version__), f"__{op}__")(parse_version(version))
