from aiogram.fsm.state import State, StatesGroup

class UserSetup(StatesGroup):
    choosing_region = State()
    choosing_group = State()
    
class AdminState(StatesGroup):
    waiting_for_broadcast = State()