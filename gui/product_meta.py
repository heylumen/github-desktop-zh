# -*- coding: utf-8 -*-
"""产品级单一事实源：应用版本与内置字典上限。

spec / build_release / verify_archive / app 都从这里读取，避免同一数字
散落在多个文件里。内置字典的实际列表仍由 dictionaries/ 目录决定。
"""

APP_VERSION = "1.0.3"
BUNDLED_DICTIONARY_LIMIT = 2
