"""
导出服务
========
问答结果 → Word 导出；节点对比 → Word 导出。
"""

import logging

logger = logging.getLogger(__name__)


class ExportService:
    """文档导出服务（Word/PDF）"""

    def export_chat_to_word(self, session_id: str, include_images: bool = True) -> str:
        """
        将问答会话导出为 Word 文档
        返回下载 URL
        """
        logger.info(f"[ExportService] export session {session_id}")
        # TODO: 实现
        return "stub_url"

    def export_comparison_to_word(self, comparison_id: str) -> str:
        """导出节点对比为 Word"""
        logger.info(f"[ExportService] export comparison {comparison_id}")
        return "stub_url"
