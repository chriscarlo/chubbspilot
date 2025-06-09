"""Dependency injection setup for Concierge application"""

from functools import lru_cache
from typing import AsyncGenerator

from openpilot.selfdrive.chauffeur.concierge.config.settings_simple import ConciergeSettings


@lru_cache()
def get_settings() -> ConciergeSettings:
    """Get application settings singleton"""
    return ConciergeSettings()


# Placeholder for future managers - will be implemented in Phase 2
async def get_zmq_manager():
    """Get ZMQ manager - placeholder for Phase 2"""
    from openpilot.selfdrive.chauffeur.concierge.core.managers.zmq_manager import ZMQManager
    return ZMQManager(get_settings())


async def get_process_manager():
    """Get process manager - placeholder for Phase 2"""
    from openpilot.selfdrive.chauffeur.concierge.core.managers.process_manager import ProcessManager
    return ProcessManager(get_settings())


async def get_log_repository():
    """Get log repository - placeholder for Phase 2"""
    from openpilot.selfdrive.chauffeur.concierge.infrastructure.repositories.log_repository import LogRepository
    return LogRepository(get_settings())


async def get_status_service():
    """Get status service - placeholder for Phase 2"""
    from openpilot.selfdrive.chauffeur.concierge.core.services.status_service import StatusService
    return StatusService(get_settings())


async def get_terminal_service():
    """Get terminal service - placeholder for Phase 2"""
    from openpilot.selfdrive.chauffeur.concierge.core.services.terminal_service import TerminalService
    session_manager = None  # Will be implemented in Phase 2
    return TerminalService(get_settings(), session_manager)


async def get_monitoring_service():
    """Get monitoring service - placeholder for Phase 2"""
    from openpilot.selfdrive.chauffeur.concierge.core.services.monitoring_service import MonitoringService
    return MonitoringService(get_settings())