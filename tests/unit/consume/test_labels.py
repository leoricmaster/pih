"""信源页呈现词映射的不变式（doc-4 术语词表「呈现」基线的代码落点）。

labels 模块的 key 集必须与 domainpacks.schema 枚举一致：schema 新增枚举而
词表未跟时此处变红（呈现层漂移守卫，非功能驱动用例）。
"""
from __future__ import annotations

from pih.consume.labels import FIELD_LEGEND, FREQ_LABELS, TYPE_LABELS
from pih.domainpacks.schema import FETCH_FREQUENCIES, SOURCE_TYPES


class TestLabelCoverageInvariants:
    def test_type_labels_cover_all_source_types(self):
        assert set(TYPE_LABELS) == set(SOURCE_TYPES)

    def test_freq_labels_cover_all_fetch_frequencies(self):
        assert set(FREQ_LABELS) == set(FETCH_FREQUENCIES)

    def test_field_legend_covers_table_columns(self):
        """图例覆盖表格中需要解释的四列（层级/可靠性/类型/频率）。"""
        names = {name for name, _ in FIELD_LEGEND}
        assert names == {"类型", "层级", "可靠性", "频率"}
