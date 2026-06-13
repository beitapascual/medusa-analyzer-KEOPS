from medusa_analyzer.backend.features.registry import get_feature_catalog
from medusa_analyzer.backend.workflows.eeg_state import EEGWorkflowState


def create_eeg_workflow_state() -> EEGWorkflowState:
    state = EEGWorkflowState()
    state.feature_config.selected_feature_ids = [
        feature.id for feature in get_feature_catalog() if feature.enabled_by_default
    ]
    return state
