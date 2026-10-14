from aiogram import Router

from .account import router as account_router
from .operations import router as operations_router
from .start import router as start_router

router = Router()
router.include_router(start_router)
router.include_router(account_router)
router.include_router(operations_router)
