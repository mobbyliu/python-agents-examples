import asyncio
import logging
import re
from typing import List, TYPE_CHECKING

from livekit.agents.llm import function_tool
from livekit.plugins import deepgram, openai, silero, inworld

from agents.base_agent import BaseGameAgent
from character import NPCCharacter, PlayerCharacter
from core.game_state import RunContext_T, GameUserData
from game_mechanics import Combat, SpellCasting, GameUtilities, CombatAction
from utils.display import Colors
from utils.prompt_loader import load_prompt

logger = logging.getLogger("dungeons-and-agents")

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
            # Clear any leftover messages in the queue to avoid repetition
            while not userdata.combat_state.action_queue.empty():
                userdata.combat_state.action_queue.get()
            
            current_char = userdata.combat_state.get_current_character()
            if current_char == userdata.player_character:
                self.session.say("It's your turn! You can attack, defend, cast a spell, use an item, or try to flee!")
            else:
                await self._queue_npc_turn()
                await self._process_action_queue()
    
    async def _process_action_queue(self):
        """Process combat actions from the queue sequentially"""
        userdata: GameUserData = self.session.userdata
        combat_state = userdata.combat_state
        
        if not combat_state:
            return
            
        while not combat_state.action_queue.empty():
            action = combat_state.action_queue.get()
            if action.delay > 0:
                await asyncio.sleep(action.delay)
            self.session.say(action.message)
            await asyncio.sleep(1.0)
    
    async def _queue_npc_turn(self):
        """Queue NPC turns for processing"""
        userdata: GameUserData = self.session.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return
        
        while True:
            current_char = combat_state.get_current_character()
            if not current_char or current_char == userdata.player_character:
                if current_char == userdata.player_character:
                    combat_state.action_queue.put(
                        CombatAction(message="It's your turn! What do you do?", delay=0.5)
                    )
                break
            
            if isinstance(current_char, NPCCharacter):
                # Process this NPC's turn and queue the action
                await self._queue_single_npc_action(current_char)
                
                # Check if combat ended
                if combat_state.is_complete:
                    break
                
                # Advance to next turn
                combat_state.next_turn()
            else:
                break
    
    async def _queue_single_npc_action(self, npc: NPCCharacter):
        """Queue a single NPC's combat action"""
        userdata: GameUserData = self.session.userdata
        combat_state = userdata.combat_state
        
        if not combat_state or combat_state.is_complete:
            return
        
        # TODO: Add a more complex AI for the NPCs
        result = Combat.perform_attack(npc, userdata.player_character)
        hit, damage, description = result
        
        # Emit combat update
        await self.emit_state_update("combat_action", {
            "action": "attack",
            "attacker": npc.name,
            "target": userdata.player_character.name,
            "hit": hit,
            "damage": damage
        })
        
        # Create a cleaner description for TTS
        if hit:
            if damage > 0:
                tts_description = f"{npc.name} strikes you for {damage} damage!"
                if userdata.player_character.current_health <= 0:
                    tts_description += " You have been defeated!"
                else:
                    health_percent = (userdata.player_character.current_health / userdata.player_character.max_health) * 100
                    if health_percent < 25:
                        tts_description += " You're badly wounded!"
                    elif health_percent < 50:
                        tts_description += " You're taking heavy damage!"
            else:
                tts_description = f"{npc.name} hits but deals no damage."
        else:
            tts_description = f"{npc.name} swings and misses!"
        
        # Queue the NPC action
        combat_state.action_queue.put(CombatAction(message=tts_description, delay=0.3))
        
        # Check if player was defeated
        if userdata.player_character.current_health <= 0:
            combat_state.is_complete = True
            userdata.game_state = "game_over"
            defeat_action = CombatAction(
                message="Your adventure ends here... for now.",
                delay=1.0
            )
            combat_state.action_queue.put(defeat_action)
            
            # Process the final message
            await self._process_action_queue()
            
            # Emit defeat update
            await self.emit_state_update("character_defeated", {
                "character": userdata.player_character.name,
                "type": "player"
            })
            
            # End the session properly
            logger.info("Player defeated - ending session")
            await self.session.say("Thank you for playing Dungeons and Agents. Until next time, brave adventurer!")
            await self.session.drain()  # Ensure all messages are sent
            await self.session.aclose()
            
            # Delete the room
            try:
                from livekit import api
                await userdata.ctx.api.room.delete_room(
                    api.DeleteRoomRequest(room=userdata.ctx.room.name)
                )
            except Exception as e:
                logger.error(f"Error deleting room: {e}")
    
    
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
            # Look for target in the initiative order to ensure we have the right reference
            for char in combat_state.initiative_order:
                if isinstance(char, NPCCharacter) and char.name.lower() == target_name.lower():
                    target = char
                    break
        
        if not target and enemies:
            target = enemies[0]  # Default to first enemy
        
        # Perform attack
        hit, damage, description = Combat.perform_attack(userdata.player_character, target)
        combat_state.combat_log.append(description)
        
        # Emit combat update
        await self.emit_state_update("combat_action", {
            "action": "attack",
            "attacker": userdata.player_character.name,
            "target": target.name,
            "hit": hit,
            "damage": damage
        })
        
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
        
        # Queue the player's attack result
        combat_state.action_queue.put(CombatAction(message=response, delay=0.0))
        
        # Check if enemy defeated
        if target.current_health <= 0:
            logger.info(f"Enemy {target.name} defeated, removing from combat")
            logger.info(f"Before removal - initiative_order: {[c.name for c in combat_state.initiative_order]}")
            logger.info(f"Combat state before removal - is_complete: {combat_state.is_complete}")
            
            combat_state.remove_defeated(target)
            userdata.current_npcs.remove(target)
            
            logger.info(f"After removal - initiative_order: {[c.name for c in combat_state.initiative_order]}")
            logger.info(f"Combat state after removal - is_complete: {combat_state.is_complete}")
            
            # Emit defeat update
            await self.emit_state_update("character_defeated", {
                "character": target.name,
                "type": "enemy"
            })
            
            # Check if combat is over
            if combat_state.is_complete:
                logger.info("Combat is complete, ending combat and returning to narrator")
                # Queue victory message and process queue before ending combat
                victory_action = CombatAction(
                    message="Victory! The battle is won!",
                    delay=0.5
                )
                combat_state.action_queue.put(victory_action)
                await self._process_action_queue()
                # End combat and switch to narrator
                result = await self._end_combat(context, victory=True)
                return result
        
        # Advance turn
        combat_state.next_turn()
        
        # Queue NPC turn processing
        await self._queue_npc_turn()
        
        # Process the action queue
        await self._process_action_queue()
        
        return "Action completed"
    
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
        
        # Queue the defend action
        combat_state.action_queue.put(CombatAction(message=description, delay=0.0))
        
        # Advance turn
        combat_state.next_turn()
        
        # Queue NPC turns and process
        await self._queue_npc_turn()
        await self._process_action_queue()
        
        return "Action completed"
    
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
        
        # Queue the spell cast result
        combat_state.action_queue.put(CombatAction(message=result, delay=0.0))
        
        # Check if any enemies defeated
        for enemy in list(self._get_active_enemies(userdata)):
            if enemy.current_health <= 0:
                combat_state.remove_defeated(enemy)
                userdata.current_npcs.remove(enemy)
        
        if combat_state.is_complete:
            victory_action = CombatAction(
                message="Victory! All enemies have been vanquished!",
                delay=0.5
            )
            combat_state.action_queue.put(victory_action)
            await self._process_action_queue()
            result = await self._end_combat(context, victory=True)
            return result
        
        # Advance turn
        combat_state.next_turn()
        
        # Queue NPC turns and process
        await self._queue_npc_turn()
        await self._process_action_queue()
        
        return "Action completed"
    
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
        
        # Queue the item use result
        combat_state.action_queue.put(CombatAction(message=result, delay=0.0))
        
        # Advance turn
        combat_state.next_turn()
        
        # Queue NPC turns and process
        await self._queue_npc_turn()
        await self._process_action_queue()
        
        return "Action completed"
    
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
        
        # Queue the flee attempt result
        combat_state.action_queue.put(CombatAction(message=description, delay=0.0))
        
        if success:
            # Process queue before ending combat
            await self._process_action_queue()
            # End combat
            result = await self._end_combat(context, victory=False, fled=True)
            return result
        else:
            # Failed - lose turn
            combat_state.combat_log.append(description)
            combat_state.next_turn()
            
            # Queue NPC turns and process
            await self._queue_npc_turn()
            await self._process_action_queue()
            
            return "Action completed"
    
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
            
            # Emit inventory update after loot collection
            await self.emit_state_update("inventory_changed", {
                "action": "loot_collected",
                "gold_gained": total_gold,
                "items_gained": len(all_loot)
            })
            
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
        userdata.active_npc = None  # Clear active NPC when combat ends
        
        # Clear defeated enemies
        userdata.current_npcs = [npc for npc in userdata.current_npcs if npc.current_health > 0]
        
        # Store current agent for context preservation
        userdata.prev_agent = self
        
        # Say the result
        self.session.say(result)
        
        # Switch back to narrator agent
        from agents.narrator_agent import NarratorAgent
        self.session.update_agent(NarratorAgent())
        
        return result
    
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