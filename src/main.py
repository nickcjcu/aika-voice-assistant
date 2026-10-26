import asyncio
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, RunContext, function_tool
from livekit.plugins import openai

from functions import (
    add_note, list_notes, remove_note,
    add_stock_request, list_stock_requests, remove_stock_request, mark_stock_ordered,
    record_food_waste, list_food_waste,
    add_checklist_task, list_checklist, complete_checklist_task, remove_checklist_task,
    report_equipment_fault, list_equipment_faults, resolve_equipment_fault,
    start_shift, current_chef, calculate_portion,
)

load_dotenv()


class AikaAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are an English-only assistant. 
You must only understand and respond in English. 
If the user speaks to you in another language, you must politely reply in English 
stating that you can only communicate in English.

You are AIKA+, a friendly AI kitchen assistant.

Help with cooking, recipes, ingredient substitutions, food preparation and kitchen questions.
Keep spoken responses clear, natural and concise. Ask a short follow up question when important
information is missing. Never claim you completed an action unless a tool confirms it.

Use the available tools for notes, stock requests, food waste, checklist tasks, equipment faults,
chef identification and portion calculations. Do not invent saved records or claim a record exists
unless a tool returns it.

For destructive actions such as removing a note, stock request or checklist task, make sure you
know the relevant record ID. If the user has not identified the record clearly, list the records
and ask which one they mean rather than deleting an arbitrary entry.

For recipes, give a simple list of ingredients followed by numbered preparation steps.
For ingredient substitutions, explain a practical substitute and mention when the result may differ.
For portion calculations, use the calculation tool when the user supplies a known ingredient amount
for a known number of servings. If they only ask how much rice or another ingredient is needed for
a number of people, ask about the dish or use a clearly labelled practical estimate rather than
presenting an estimate as exact.

Timers and reminders run only while this AIKA+ agent process is running. If the process stops,
pending timers and reminders will be lost. Ask for the duration in minutes and seconds if unclear.
When a timer or reminder expires, announce it clearly.
            """,
        )
        self._scheduled_tasks: set[asyncio.Task] = set()

    def _schedule_announcement(self, seconds: int, message: str) -> None:
        task = asyncio.create_task(self._wait_and_announce(seconds, message))
        self._scheduled_tasks.add(task)
        task.add_done_callback(self._scheduled_tasks.discard)

    async def _wait_and_announce(self, seconds: int, message: str) -> None:
        try:
            await asyncio.sleep(seconds)
            await self.session.generate_reply(instructions=f"Announce this alert to the user clearly and briefly: {message}")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"AIKA alert error: {exc}")

    @function_tool()
    async def set_timer(self, context: RunContext, minutes: int, seconds: int = 0) -> str:
        """Set a kitchen timer for the given number of minutes and seconds."""
        total = minutes * 60 + seconds
        if minutes < 0 or seconds < 0 or seconds >= 60 or total <= 0:
            return "Please provide a duration greater than zero, with seconds between 0 and 59."
        self._schedule_announcement(total, f"Your {minutes} minute and {seconds} second timer has finished.")
        return f"Timer set for {minutes} minutes and {seconds} seconds."

    @function_tool()
    async def set_reminder(self, context: RunContext, minutes: int, seconds: int = 0, reminder: str = "") -> str:
        """Set a spoken reminder after the specified number of minutes and seconds."""
        total = minutes * 60 + seconds
        reminder = reminder.strip()
        if minutes < 0 or seconds < 0 or seconds >= 60 or total <= 0:
            return "Please provide a duration greater than zero, with seconds between 0 and 59."
        if not reminder:
            return "What would you like me to remind you about?"
        self._schedule_announcement(total, f"Reminder: {reminder}.")
        return f"I'll remind you in {minutes} minutes and {seconds} seconds: {reminder}."

    @function_tool()
    async def save_note(self, context: RunContext, note: str) -> str:
        """Save a kitchen note."""
        return add_note(note)

    @function_tool()
    async def read_notes(self, context: RunContext) -> str:
        """Read and list all saved kitchen notes."""
        return list_notes()

    @function_tool()
    async def delete_note(self, context: RunContext, note_id: int) -> str:
        """Delete a specific saved kitchen note using its ID."""
        return remove_note(note_id)

    @function_tool()
    async def create_stock_request(self, context: RunContext, item: str, quantity: str) -> str:
        """Add an item and quantity to the kitchen stock request list."""
        return add_stock_request(item, quantity)

    @function_tool()
    async def read_stock_requests(self, context: RunContext) -> str:
        """List all stock requests and their status."""
        return list_stock_requests()

    @function_tool()
    async def delete_stock_request(self, context: RunContext, request_id: int) -> str:
        """Remove a stock request by its ID."""
        return remove_stock_request(request_id)

    @function_tool()
    async def mark_request_ordered(self, context: RunContext, request_id: int) -> str:
        """Mark a stock request as ordered by its ID."""
        return mark_stock_ordered(request_id)

    @function_tool()
    async def log_food_waste(self, context: RunContext, item: str, quantity: str, waste_date: str = "", details: str = "") -> str:
        """Record wasted food, quantity and optional date. Use YYYY-MM-DD for a specified date; leave blank for today."""
        return record_food_waste(item, quantity, waste_date, details)

    @function_tool()
    async def read_food_waste(self, context: RunContext, waste_date: str = "") -> str:
        """List food waste recorded for a date. Leave date blank for today. Use YYYY-MM-DD for a specified date."""
        return list_food_waste(waste_date)

    @function_tool()
    async def add_checklist_item(self, context: RunContext, task: str, category: str = "General") -> str:
        """Add a kitchen checklist task, for example category Opening or Closing."""
        return add_checklist_task(task, category)

    @function_tool()
    async def read_checklist(self, context: RunContext, category: str = "", incomplete_only: bool = False) -> str:
        """List kitchen checklist tasks. Optionally filter by category such as Opening and optionally show incomplete tasks only."""
        return list_checklist(category, incomplete_only)

    @function_tool()
    async def complete_checklist_item(self, context: RunContext, task_id: int) -> str:
        """Mark a checklist task complete by its ID."""
        return complete_checklist_task(task_id)

    @function_tool()
    async def delete_checklist_item(self, context: RunContext, task_id: int) -> str:
        """Remove a checklist task by its ID."""
        return remove_checklist_task(task_id)

    @function_tool()
    async def report_fault(self, context: RunContext, equipment: str, description: str) -> str:
        """Record a kitchen equipment fault and mark it open."""
        return report_equipment_fault(equipment, description)

    @function_tool()
    async def read_faults(self, context: RunContext, open_only: bool = True) -> str:
        """List equipment faults. Set open_only true to list unresolved faults only."""
        return list_equipment_faults(open_only)

    @function_tool()
    async def resolve_fault(self, context: RunContext, fault_id: int) -> str:
        """Mark an open equipment fault as resolved by its ID."""
        return resolve_equipment_fault(fault_id)

    @function_tool()
    async def identify_chef(self, context: RunContext, chef_name: str) -> str:
        """Record which chef is starting the current shift."""
        return start_shift(chef_name)

    @function_tool()
    async def who_is_chef(self, context: RunContext) -> str:
        """Identify the chef recorded as working the current shift."""
        return current_chef()

    @function_tool()
    async def calculate_ingredient_portion(self, context: RunContext, ingredient: str, amount: float, unit: str, base_servings: int, target_servings: int) -> str:
        """Scale an ingredient amount from a known base serving count to a target serving count."""
        return calculate_portion(ingredient, amount, unit, base_servings, target_servings)


server = AgentServer()


@server.rtc_session(agent_name="aika-assistant")
async def aika_assistant(ctx: agents.JobContext):
    session = AgentSession(
        llm=openai.realtime.RealtimeModel(voice="marin"),
    )

    await session.start(
        room=ctx.room,
        agent=AikaAssistant(),
    )

    await session.generate_reply(
        instructions="Greet the user and briefly introduce yourself as AIKA+, their kitchen assistant."
    )


if __name__ == "__main__":
    agents.cli.run_app(server)
