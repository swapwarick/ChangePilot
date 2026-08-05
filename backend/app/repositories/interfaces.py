from abc import ABC, abstractmethod


class SourceRepositoryAdapter(ABC):
    @abstractmethod
    async def fetch_changed_files(self, repository_id: str, base_ref: str, head_ref: str) -> list[str]:
        raise NotImplementedError

