from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseLLMProvider(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def investigate_exception(
        self,
        exception: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        pass
