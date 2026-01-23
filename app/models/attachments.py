from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from models.base import Base


class PromptAttachments(Base):
    __tablename__ = "prompt_attachments"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    prompt_history_id = Column(Integer, ForeignKey("prompt_history.id"), nullable=False)
    attachments_data = Column(Text, nullable=True)
    generated_images = Column(Text, nullable=True)
    status = Column(String(40), nullable=True)

    created_on = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self):
        return (
            f"<PromptAttachments(id={self.id}, "
            f"prompt_history_id={self.prompt_history_id})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "prompt_history_id": self.prompt_history_id,
            "attachments": self.attachments_data,
            "generated_images": self.generated_images,
            "created_on": self.created_on.isoformat() if self.created_on else None,
        }
