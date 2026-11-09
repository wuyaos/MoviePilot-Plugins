"""失败清理事件兼容入口；功能已停用，不执行删除。"""
def handle_transfer_failed_event(plugin, event):
    return {"disabled": True, "deleted": 0, "skipped": 1}
