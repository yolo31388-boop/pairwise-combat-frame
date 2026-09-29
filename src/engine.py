"""技能连招帧取消 - 带9个bug"""
from dataclasses import dataclass, field

@dataclass
class SkillFrame:
    sid: str
    startup: int  # 出招帧
    active: int   # 判定帧
    recovery: int # 收招帧
    cancel_start: int
    cancel_end: int
    damage: int
    cost: int = 0

class CombatSystem:
    def __init__(self):
        self.skills: dict[str, SkillFrame] = {}
        self.current_skill = None
        self.current_frame = 0
        self.hit_confirmed = False
        self.super_armor = 0  # bug7: 布尔值
        self.stamina = 100

    def start_skill(self, sid):
        skill = self.skills[sid]
        self.current_skill = sid
        self.current_frame = 0
        self.hit_confirmed = False
        # bug6: 开始就扣CD
        return True

    def try_cancel(self):
        # bug2: 不检查取消窗口
        if self.current_skill:
            self.current_skill = None
            return True
        return False

    def can_chain(self, next_sid):
        # bug3: 不检查命中
        return self.current_skill is not None

    def is_damage_frame(self):
        # bug4: 伤害帧=判定帧
        skill = self.skills[self.current_skill]
        return skill.startup <= self.current_frame <= skill.startup + skill.active

    def hit_stun(self, damage, direction):
        # bug5: 不区分方向
        return 20

    def break_super_armor(self, damage):
        # bug7: 一次破霸体
        self.super_armor = 0
        return True

    def tick(self):
        self.current_frame += 1
        # bug8: 浮点时间
