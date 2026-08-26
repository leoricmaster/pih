"""信源适配器子包：导入即完成内置适配器注册（base.py 注册表）。

调用方（cli/run/probe/测试）import 本包即可按 source.id / source.type 取适配器，
无需逐模块 noqa 导入。
"""
from . import ccma, cehome, sany  # noqa: F401
