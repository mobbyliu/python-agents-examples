import asyncio
import re
from typing import List, TYPE_CHECKING

from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, openai, silero, inworld

from agents.base_agent import BaseGameAgent
from character import NPCCharacter, PlayerCharacter
from core.game_state import RunContext_T, GameUserData
from game_mechanics import Combat, SpellCasting, GameUtilities
from utils.display import Colors
from utils.prompt_loader import load_prompt

if TYPE_CHECKING:
    from agents.narrator_agent import NarratorAgent


class CombatAgent(BaseGameAgent):
    """Handles combat encounters with fast-paced action"""
    
    def __init__(self) -> None:
        super().__init__(
            instructions=load_prompt('combat_prompt.yaml'),
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o"),
            tts=inworld.TTS(voice="Hades"),
            vad=silero.VAD.load()
        )
    
    async def on_enter(self) -> None:
        await super().on_enter()
        userdata: GameUserData = self.session.userdata
        
        if userdata.combat_state and not userdata.combat_state.is_complete:
            current_char = userdata.combat_state.get_current_character()
            if current_char == userdata.player_character:
                self.session.say("It's your turn! You can attack, defend, cast a spell, use an item, or try to flee!")
            else:
                # Process NPC turn
                await self._process_npc_turn()
    
    async def _process_npc_turn(self):
        """Process an NPC's combat turn"""
        userdata: GameUserData = self.session.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return
        
        current_npc = combat_state.get_current_character()
        if not isinstance(current_npc, NPCCharacter):
            return
        
        # Simple AI: Attack the player
        result = Combat.perform_attack(current_npc, userdata.player_character)
        hit, damage, description = result
        
        # Create a cleaner description for TTS
        if hit:
            if damage > 0:
                tts_description = f"{current_npc.name} strikes you for {damage} damage!"
                if userdata.player_character.current_health <= 0:
                    tts_description += " You have been defeated!"
                else:
                    health_percent = (userdata.player_character.current_health / userdata.player_character.max_health) * 100
                    if health_percent < 25:
                        tts_description += " You're badly wounded!"
                    elif health_percent < 50:
                        tts_description += " You're taking heavy damage!"
            else:
                tts_description = f"{current_npc.name} hits but deals no damage."
        else:
            tts_description = f"{current_npc.name} swings and misses!"
        
        self.session.say(tts_description)
        
        # Check if player was defeated
        if userdata.player_character.current_health <= 0:
            combat_state.is_complete = True
            userdata.game_state = "game_over"
            await asyncio.sleep(2)  # Let the defeat message play
            self.session.say("Your adventure ends here... for now.")
            return
        
        # Advance turn
        combat_state.next_turn()
        await asyncio.sleep(1.5)  # Brief pause for pacing
        
        # Check next turn
        next_char = combat_state.get_current_character()
        if next_char == userdata.player_character:
            self.session.say("It's your turn! What do you do?")
        else:
            # Continue with next NPC
            await self._process_npc_turn()
    
    @function_tool
    async def attack(self, context: RunContext_T, target_name: str = None):
        """Attack an enemy"""
        userdata = context.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return "You're not in combat!"
        
        # Verify it's player's turn
        if combat_state.get_current_character() != userdata.player_character:
            return "It's not your turn!"
        
        # Find target
        enemies = self._get_active_enemies(userdata)
        if not enemies:
            return "No enemies to attack!"
        
        target = None
        if target_name:
            for enemy in enemies:
                if enemy.name.lower() == target_name.lower():
                    target = enemy
                    break
        
        if not target:
            target = enemies[0]  # Default to first enemy
        
        # Perform attack
        hit, damage, description = Combat.perform_attack(userdata.player_character, target)
        combat_state.combat_log.append(description)
        
        # Create cleaner response for TTS
        if hit:
            if damage > 0:
                response = f"You hit {target.name} for {damage} damage!"
                if target.current_health <= 0:
                    response += f" {target.name} has been defeated!"
                else:
                    response += f" {target.name} has {target.current_health} health remaining."
            else:
                response = f"You hit {target.name} but deal no damage."
        else:
            response = f"You swing at {target.name} but miss!"
        
        # Check if enemy defeated
        if target.current_health <= 0:
            combat_state.remove_defeated(target)
            userdata.current_npcs.remove(target)
            
            # Check if combat is over
            if combat_state.is_complete:
                return await self._end_combat(context, victory=True)
        
        # Advance turn and process NPC turns
        combat_state.next_turn()
        
        # Schedule NPC turn processing
        asyncio.create_task(self._process_npc_turn())
        
        return response
    
    @function_tool
    async def defend(self, context: RunContext_T):
        """Take a defensive stance"""
        userdata = context.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return "You're not in combat!"
        
        if combat_state.get_current_character() != userdata.player_character:
            return "It's not your turn!"
        
        # Temporary AC boost (would need to track this properly in real implementation)
        description = Combat.perform_defend(userdata.player_character)
        combat_state.combat_log.append(description)
        
        # Advance turn
        combat_state.next_turn()
        asyncio.create_task(self._process_npc_turn())
        
        return description
    
    @function_tool
    async def cast_spell(self, context: RunContext_T, spell_name: str, target_name: str = None):
        """Cast a spell"""
        userdata = context.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return "You're not in combat!"
        
        if combat_state.get_current_character() != userdata.player_character:
            return "It's not your turn!"
        
        # Find target if needed
        target = None
        if target_name:
            if target_name.lower() == "self" or target_name.lower() == userdata.player_character.name.lower():
                target = userdata.player_character
            else:
                for enemy in self._get_active_enemies(userdata):
                    if enemy.name.lower() == target_name.lower():
                        target = enemy
                        break
        
        # Cast spell
        result = SpellCasting.cast_spell(userdata.player_character, spell_name.lower(), target)
        combat_state.combat_log.append(result)
        
        # Check if any enemies defeated
        for enemy in list(self._get_active_enemies(userdata)):
            if enemy.current_health <= 0:
                combat_state.remove_defeated(enemy)
                userdata.current_npcs.remove(enemy)
        
        if combat_state.is_complete:
            return await self._end_combat(context, victory=True)
        
        # Advance turn
        combat_state.next_turn()
        asyncio.create_task(self._process_npc_turn())
        
        return result
    
    @function_tool
    async def use_combat_item(self, context: RunContext_T, item_name: str):
        """Use an item during combat"""
        userdata = context.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return "You're not in combat!"
        
        if combat_state.get_current_character() != userdata.player_character:
            return "It's not your turn!"
        
        # Delegate to narrator's use_item but in combat context
        from agents.narrator_agent import NarratorAgent
        narrator = NarratorAgent()
        result = await narrator.use_item(context, item_name)
        
        combat_state.combat_log.append(result)
        
        # Advance turn
        combat_state.next_turn()
        asyncio.create_task(self._process_npc_turn())
        
        return result
    
    @function_tool
    async def flee_combat(self, context: RunContext_T):
        """Attempt to flee from combat"""
        userdata = context.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return "You're not in combat!"
        
        if combat_state.get_current_character() != userdata.player_character:
            return "It's not your turn!"
        
        enemies = self._get_active_enemies(userdata)
        success, description = Combat.attempt_flee(userdata.player_character, enemies)
        
        if success:
            # End combat
            return await self._end_combat(context, victory=False, fled=True)
        else:
            # Failed - lose turn
            combat_state.combat_log.append(description)
            combat_state.next_turn()
            asyncio.create_task(self._process_npc_turn())
            
            return description
    
    async def _end_combat(self, context: RunContext_T, victory: bool, fled: bool = False):
        """End combat and return to narrator"""
        userdata = context.userdata
        
        if victory and not fled:
            # Calculate rewards
            total_xp = sum(enemy.level * 50 for enemy in userdata.current_npcs if enemy.current_health <= 0)
            all_loot = []
            total_gold = 0
            
            # Transfer loot from defeated enemies
            for enemy in userdata.current_npcs:
                if enemy.current_health <= 0:
                    loot_desc = GameUtilities.transfer_loot(enemy, userdata.player_character)
                    if "gold" in loot_desc:
                        # Extract gold amount for total
                        gold_match = re.search(r'(\d+) gold', loot_desc)
                        if gold_match:
                            total_gold += int(gold_match.group(1))
                    
                    # Also add any specific items mentioned
                    if loot_desc != "The enemy had nothing of value.":
                        all_loot.append(f"From {enemy.name}: {loot_desc}")
            
            # Grant experience
            level_up_msg = userdata.player_character.gain_experience(total_xp)
            
            result = f"Victory! You earned {total_xp} experience points."
            if level_up_msg:
                result += f" {level_up_msg}"
            if all_loot:
                result += f"\n\nLoot collected:\n" + "\n".join(all_loot)
            
            # Print loot summary to console
            if all_loot or total_gold > 0:
                print(f"\n{Colors.YELLOW}{'💰' * 20}{Colors.ENDC}")
                print(f"{Colors.BOLD}📦 LOOT COLLECTED{Colors.ENDC}")
                if total_gold > 0:
                    print(f"{Colors.BOLD}   Gold: {Colors.YELLOW}{total_gold}{Colors.ENDC}")
                for loot_line in all_loot:
                    if "gold" not in loot_line.lower() or "item" in loot_line.lower():
                        print(f"   {loot_line}")
                print(f"{Colors.YELLOW}{'💰' * 20}{Colors.ENDC}\n")
            
            userdata.add_story_event(f"Won combat - gained {total_xp} XP")
        elif fled:
            result = "You successfully fled from combat!"
            userdata.add_story_event("Fled from combat")
        else:
            result = "You have been defeated..."
            userdata.game_state = "game_over"
        
        # Clean up combat state
        userdata.combat_state = None
        userdata.game_state = "exploration" if victory or fled else "game_over"
        userdata.current_agent_type = "narrator"
        
        # Clear defeated enemies
        userdata.current_npcs = [npc for npc in userdata.current_npcs if npc.current_health > 0]
        
        # Store current agent for context preservation
        userdata.prev_agent = self
        
        # Return narrator agent
        from agents.narrator_agent import NarratorAgent
        return NarratorAgent()
    
    @function_tool
    async def check_combat_status(self, context: RunContext_T):
        """Check the current combat status"""
        userdata = context.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return "You're not in combat!"
        
        status = f"Round {combat_state.round_number}\n"
        status += f"Turn order: {', '.join(c.name for c in combat_state.initiative_order)}\n"
        status += f"Current turn: {combat_state.get_current_character().name}\n\n"
        
        # Character statuses
        for char in combat_state.initiative_order:
            status += char.get_status_description() + "\n"
        
        return status