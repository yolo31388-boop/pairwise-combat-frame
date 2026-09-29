"""连招测试"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.engine import CombatSystem, SkillFrame

class TestCancel:
    def test_cancel_window_enforced(self):
        cs = CombatSystem()
        cs.skills["a"] = SkillFrame("a", 5, 3, 20, 8, 15, 100)
        cs.start_skill("a")
        cs.current_frame = 2  # 出招中，不能取消
        assert not cs.try_cancel(), "取消窗口未限制"

class TestChain:
    def test_chain_requires_hit(self):
        cs = CombatSystem()
        cs.skills["a"] = SkillFrame("a", 5, 3, 20, 8, 15, 100)
        cs.skills["b"] = SkillFrame("b", 5, 3, 20, 8, 15, 100)
        cs.start_skill("a")
        cs.hit_confirmed = False
        assert not cs.can_chain("b"), "连招未检查命中"
