from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class ModelCard:
    model_name: str
    model_version: str
    intended_use: str
    source_project: str
    primary_metric: str
    known_limitations: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)
