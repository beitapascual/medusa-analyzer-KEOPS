from medusa_analyzer.backend.features.registry import (
    get_default_feature_ids_for_experiment)
from medusa_analyzer.backend.workflows.eeg_state import EEGWorkflowState


def create_eeg_workflow_state() -> EEGWorkflowState:
    state = EEGWorkflowState()
    state.feature_config.selected_feature_ids = (
        get_default_feature_ids_for_experiment("eeg"))
    return state
