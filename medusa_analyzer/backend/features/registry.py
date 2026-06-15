from .descriptors import FEATURES, FeatureDescriptor


def get_feature_catalog() -> list[FeatureDescriptor]:
    return list(FEATURES)


def get_features_for_experiment(experiment_id: str) -> list[FeatureDescriptor]:
    return [
        feature
        for feature in FEATURES
        if experiment_id in feature.compatible_experiments
    ]


def get_default_feature_ids_for_experiment(experiment_id: str) -> list[str]:
    return [
        feature.id
        for feature in get_features_for_experiment(experiment_id)
        if experiment_id in feature.enabled_by_default_for
    ]
