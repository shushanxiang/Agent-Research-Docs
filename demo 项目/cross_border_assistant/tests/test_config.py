# -*- coding: utf-8 -*-
"""config.py 测试：配置常量、图片参数、环境变量读取优先级"""
import config


def test_llm_config_exist():
    assert hasattr(config, "DASHSCOPE_API_KEY")
    assert config.LLM_MODEL_NAME, "LLM_MODEL_NAME 不应为空"
    assert config.VL_MODEL_NAME, "VL_MODEL_NAME 不应为空"
    assert config.IMAGE_GEN_MODEL, "IMAGE_GEN_MODEL 不应为空"


def test_image_gen_config_valid():
    cfg = config.IMAGE_GEN_CONFIG
    assert cfg["width"] > 0
    assert cfg["height"] > 0
    assert cfg["n"] >= 1


def test_paths_configured():
    assert config.DB_PATH.endswith(".db")
    assert config.SENSITIVE_WORDS_FILE.endswith(".txt")


# ---------- 环境变量读取（系统级 Machine 优先） ----------

def test_get_env_prefers_machine(monkeypatch):
    """系统级(Machine)存在时优先于进程环境"""
    monkeypatch.setattr(config, "_read_machine_env", lambda name: "sk-machine-key")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-user-key")
    assert config._get_env("DASHSCOPE_API_KEY") == "sk-machine-key"


def test_get_env_fallback_to_process(monkeypatch):
    """系统级为空时回退到进程环境（含用户级）"""
    monkeypatch.setattr(config, "_read_machine_env", lambda name: "")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-user-key")
    assert config._get_env("DASHSCOPE_API_KEY") == "sk-user-key"


def test_get_env_empty_when_unset(monkeypatch):
    """系统级与进程环境均未配置时返回空字符串（不再有假占位符）"""
    monkeypatch.setattr(config, "_read_machine_env", lambda name: "")
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    assert config._get_env("DASHSCOPE_API_KEY") == ""


def test_read_machine_env_handles_failure(monkeypatch):
    """注册表读取异常时返回空串，不抛错"""
    import sys
    import types

    fake_winreg = types.ModuleType("winreg")

    def fake_open(*args):
        raise OSError("permission denied")

    fake_winreg.OpenKey = fake_open
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)
    assert config._read_machine_env("DASHSCOPE_API_KEY") == ""
