from abc import ABC


class EntityNotFoundException(Exception, ABC):
    entity_id: str
    entity_name: str

    def get_message(self) -> str:
        return f"Entity {self.entity_name} with ID {self.entity_id} not found."