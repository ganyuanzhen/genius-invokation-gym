"""Base class of each character: abstract class
A character in the game should be an instant of the specific character class defined in each file"""
from abc import ABC, abstractmethod
from collections import OrderedDict
from queue import PriorityQueue
from typing import cast

from gisim.cards.characters.base import (
    CHARACTER_CARDS,
    CHARACTER_NAME2ID,
    CHARACTER_SKILLS,
)

from .entity import Entity
from .enums import *
from .message import (
    ChangeCharacterMsg,
    CharacterDiedMsg,
    DealDamageMsg,
    Message,
    UseSkillMsg,
)


class CharacterEntity(Entity):
    def __init__(self, name: str, player_id: PlayerID, position: CharPos):
        super().__init__()
        self.player_id = player_id
        self.position = position
        self.name = name
        self.active = False
        self.alive = True
        """ Whether this character in set forward. There should be only one character in the active state for each player"""
        self.elemental_infusion = ElementType.NONE
        """普通攻击元素附魔"""
        self.elemental_attachment = ElementType.NONE
        """角色元素附着"""

        # Initialize Character from its card template
        self.id = CHARACTER_NAME2ID[name]
        self.character_card = CHARACTER_CARDS[self.id].copy()
        self.element_type = self.character_card.element_type
        self.nationalities = self.character_card.nations
        self.weapon_type = self.character_card.weapon_type
        """Should be either one of `bow`, `claymore`, `sword`, `polearm`, `catalyst`
            应当为`弓`,`双手剑`,`单手剑`,`长柄武器`,`法器`中的一个"""
        self.skills = self.character_card.skills.copy()
        """The content of their skills should be modifiable (e.g. The cost will be affected by artifacts and the basic damage by weapon, talent).
        """
        self.skill_num = len(self.skills)
        self.skill_names = [skill.name for skill in self.skills]
        self.health_point = self.character_card.health_point
        self.power = self.character_card.power
        self.max_power = self.character_card.max_power

    def encode(self):
        properties = [
            "name",
            "active",
            "alive",
            "elemental_infusion",
            "elemental_attachment",
            "health_point",
            "power",
            "max_power",
        ]
        return {key: getattr(self, key) for key in properties}

    def get_raw_skill(self, id=None, skill_name=None, skill_type=None):
        """Get the character's skill through either id (0, 1, 2, ...), name (str), or skill_type
        Returns:
            raw_skill (Skill): a Skill object with raw cost and effects (has not been affected by any discounts/enhancement)
        """
        if id is not None:
            assert (
                0 <= id <= self.skill_num - 1
            ), f"id should be from 0 to {self.skill_num-1}"
            return self.skills[id]
        elif skill_name is not None:
            if skill_name in self.skill_names:
                return self.skills[self.skill_names.index(skill_name)]
            else:
                assert (
                    False
                ), f"Skill {skill_name} does not exist in {self.name}'s skill set"
        else:
            assert skill_type is not None, "Should provide either skill id or its name"

    def msg_handler(self, msg_queue: PriorityQueue[Message]):
        """Will respond to `UseSkillMsg` etc."""
        msg = msg_queue.queue[0]
        if self._uuid in msg.responded_entities:
            return False
        updated = False
        if isinstance(msg, UseSkillMsg):
            msg = cast(UseSkillMsg, msg)
            if msg.user_pos == self.position:
                msg_queue.get()  # Destroy this message
                updated = True
                target_player, target_pos = msg.skill_target[0]
                # msg.skill_name #TODO: specify the name of each skill
                msg_queue.put(
                    DealDamageMsg(
                        sender_id=self.player_id,
                        targets=[(target_player, target_pos, ElementType.NONE, 2)],
                        elemental_reaction_triggered=ElementalReactionType.NONE,
                    )
                )
        elif isinstance(msg, ChangeCharacterMsg):
            msg = cast(ChangeCharacterMsg, msg)
            if self.player_id == msg.target[0]:
                if self.position == msg.target[1]:
                    self.active = True
                    updated = True
                    msg.responded_entities.append(self._uuid)
                elif self.position != msg.target[1] and self.active:
                    self.active = False
                    updated = True
                    msg.responded_entities.append(self._uuid)

        elif isinstance(msg, DealDamageMsg):
            msg = cast(DealDamageMsg, msg)
            for target_id, target_pos, element_type, dmg_val in msg.targets:
                if self.player_id == target_id and self.position == target_pos:
                    self.health_point -= min(self.health_point, dmg_val)
                    if self.health_point == 0:
                        self.alive = False
                        # self.active = False
                        dead_msg = CharacterDiedMsg(
                            sender_id=self.player_id,
                            target=(self.player_id, self.position),
                        )
                        msg_queue.put(dead_msg)
                    # TODO: add elemental reaction effects
                    msg.responded_entities.append(self._uuid)
                    updated = True
        return updated


class Skill(ABC):
    def __init__(self, name: str, cost: dict[ElementType, int], skill_type: SkillType):
        """
        Args:
        cost(dict[ElementType, int]): {ElementType:cost}; `None` if no cost is required (Please do not use empty dictionary!)
        skill_type(bool): passive skill which can only be triggered
        """
        self.name = name
        self.RAW_COST = cost
        self.TYPE = skill_type
        self.current_cost = cost

    @property
    @abstractmethod
    def requirements(self):
        """Description of the requirement of the skill in domain-specific language (dsl)."""
        ...

    @property
    @abstractmethod
    def targets(self):
        """Description of the target of the skill in domain-specific language (dsl).
        Use a list to assign multiple targets.
        """
        ...

    @property
    @abstractmethod
    def effects(self):
        """Description of the target of the skill in domain-specific language (dsl).
        Use a list to assign multiple effects to the targets respectively."""
        ...


class CharacterEntityInfo:
    def __init__(self, character_entity_info_dict: OrderedDict):
        self.name: str = character_entity_info_dict["name"]
        self.active: bool = character_entity_info_dict["active"]
        self.alive: bool = character_entity_info_dict["alive"]
        self.elemental_infusion: ElementType = character_entity_info_dict[
            "elemental_infusion"
        ]
        self.elemental_attachment: ElementType = character_entity_info_dict[
            "elemental_attachment"
        ]
        self.health_point: int = character_entity_info_dict["health_point"]
        self.power: int = character_entity_info_dict["power"]
        self.max_power: int = character_entity_info_dict["max_power"]
