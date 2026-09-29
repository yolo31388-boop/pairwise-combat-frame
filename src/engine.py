"""技能连招帧取消系统

修复的 9 个问题:
1. 硬直拆分为出招硬直(startup)与收招硬直(recovery), 各自按技能配置
2. 取消窗口有明确的起止帧 [cancel_start, cancel_end], 窗外不能取消
3. 连招前置检查要求上一技能确认命中, 且命中类型与下一技能要求匹配
4. 伤害帧(damage_frame)与判定帧(active)分离, 精确到单帧触发
5. 受击硬直按攻击方向(direction)与部位(part)取不同值
6. 冷却在技能生效(命中或自然结束)时才开始, 取消/打断不白扣 CD
7. 霸体为护甲值, 受伤消耗护甲, 归零才破
8. 帧数据全部使用整数帧计数, 与帧率解耦
9. 取消消耗精力(cancel_cost), 精力有限不能无限取消
"""
from dataclasses import dataclass, field


@dataclass
class SkillFrame:
    sid: str
    startup: int        # 出招硬直(帧)
    active: int         # 判定帧数
    recovery: int       # 收招硬直(帧)
    cancel_start: int   # 取消窗口起始帧(含)
    cancel_end: int     # 取消窗口结束帧(含)
    damage: int
    cost: int = 0
    damage_frame: int = 0        # 伤害帧: 判定窗内第几帧结算伤害
    hit_type: str = "normal"     # 本技能命中时产生的命中类型
    chain_hit_type: str = ""     # 接本技能所需的命中类型, "" 表示任意
    cooldown: int = 0            # 冷却帧数, 技能生效后才开始转
    cancel_cost: int = 20        # 取消后摇消耗的精力

    @property
    def total_frames(self) -> int:
        return self.startup + self.active + self.recovery


# 受击硬直表: 部位基础值 x 方向倍率, 全程整数帧
_HIT_STUN_BASE = {"torso": 20, "head": 30, "limb": 10}
_HIT_STUN_DIR_PERMILLE = {"front": 1000, "back": 1500, "side": 1200}


class CombatSystem:
    def __init__(self, super_armor: int = 0, stamina: int = 100):
        self.skills: dict[str, SkillFrame] = {}
        self.current_skill = None
        self.current_frame = 0          # 整数帧计数, 与帧率无关
        self.hit_confirmed = False
        self.hit_type = None
        self.super_armor = super_armor  # 霸体护甲值
        self.stamina = stamina
        self.max_stamina = stamina
        self.cooldowns: dict[str, int] = {}
        self._cooling = set()           # 已开始转 CD 的技能

    # ---- 技能生命周期 ----

    def start_skill(self, sid):
        skill = self.skills[sid]
        if self.cooldowns.get(sid, 0) > 0:
            return False
        if self.stamina < skill.cost:
            return False
        self.stamina -= skill.cost
        self.current_skill = sid
        self.current_frame = 0
        self.hit_confirmed = False
        self.hit_type = None
        return True

    def _start_cooldown(self, sid):
        if sid in self._cooling:
            return
        cd = self.skills[sid].cooldown
        if cd > 0:
            self.cooldowns[sid] = cd
            self._cooling.add(sid)

    def _end_skill(self):
        # 技能自然结束: 生效, 开始转 CD
        self._start_cooldown(self.current_skill)
        self.current_skill = None
        self.current_frame = 0

    # ---- 硬直阶段 (bug1: 出招/收招分段) ----

    def in_startup(self):
        return self.current_skill is not None and \
            self.current_frame < self.skills[self.current_skill].startup

    def in_recovery(self):
        if self.current_skill is None:
            return False
        skill = self.skills[self.current_skill]
        return self.current_frame >= skill.startup + skill.active

    def can_act(self):
        # 出招/收招硬直期间不能行动
        return self.current_skill is None

    # ---- 取消 (bug2 窗口 + bug9 资源消耗) ----

    def try_cancel(self):
        if self.current_skill is None:
            return False
        skill = self.skills[self.current_skill]
        if not (skill.cancel_start <= self.current_frame <= skill.cancel_end):
            return False
        if self.stamina < skill.cancel_cost:
            return False
        self.stamina -= skill.cancel_cost
        # 取消发生在生效前, 不触发 CD
        self.current_skill = None
        self.current_frame = 0
        return True

    # ---- 连招 (bug3: 必须命中且命中类型匹配) ----

    def confirm_hit(self, hit_type=None):
        if self.current_skill is None:
            return False
        skill = self.skills[self.current_skill]
        self.hit_confirmed = True
        self.hit_type = hit_type if hit_type is not None else skill.hit_type
        # 命中即生效: 开始转 CD
        self._start_cooldown(self.current_skill)
        return True

    def can_chain(self, next_sid):
        if self.current_skill is None or not self.hit_confirmed:
            return False
        nxt = self.skills[next_sid]
        if nxt.chain_hit_type and nxt.chain_hit_type != self.hit_type:
            return False
        return True

    # ---- 伤害帧 (bug4: 与判定帧分离, 精确单帧) ----

    def is_damage_frame(self):
        if self.current_skill is None:
            return False
        skill = self.skills[self.current_skill]
        return self.current_frame == skill.startup + skill.damage_frame

    def in_active_window(self):
        if self.current_skill is None:
            return False
        skill = self.skills[self.current_skill]
        return skill.startup <= self.current_frame < skill.startup + skill.active

    # ---- 受击硬直 (bug5: 方向 + 部位) ----

    def hit_stun(self, damage, direction="front", part="torso"):
        base = _HIT_STUN_BASE.get(part, _HIT_STUN_BASE["torso"])
        permille = _HIT_STUN_DIR_PERMILLE.get(direction, 1000)
        return base * permille // 1000

    # ---- 霸体 (bug7: 护甲值, 归零才破) ----

    def set_super_armor(self, value):
        self.super_armor = value

    def break_super_armor(self, damage):
        if self.super_armor <= 0:
            return True
        self.super_armor -= damage
        if self.super_armor <= 0:
            self.super_armor = 0
            return True
        return False

    # ---- 帧推进 (bug8: 整数帧) ----

    def tick(self):
        self.current_frame += 1
        for sid in list(self.cooldowns):
            self.cooldowns[sid] -= 1
            if self.cooldowns[sid] <= 0:
                del self.cooldowns[sid]
                self._cooling.discard(sid)
        if self.stamina < self.max_stamina:
            self.stamina += 1
        if self.current_skill is not None:
            skill = self.skills[self.current_skill]
            if self.current_frame >= skill.total_frames:
                self._end_skill()
