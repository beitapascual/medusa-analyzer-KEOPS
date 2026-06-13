from medusa_analyzer.backend.configs.features import FeatureDescriptor


FEATURES = [
    FeatureDescriptor("mean", "Mean", "Temporal", "Average signal amplitude.", True),
    FeatureDescriptor("median", "Median", "Temporal", "Robust central tendency."),
    FeatureDescriptor("variance", "Variance", "Temporal", "Signal amplitude dispersion.", True),
    FeatureDescriptor("skewness", "Skewness", "Temporal", "Distribution asymmetry."),
    FeatureDescriptor("kurtosis", "Kurtosis", "Temporal", "Distribution tail weight."),
    FeatureDescriptor("absolute_power", "Absolute power", "Spectral", "Power in each enabled band.", True),
    FeatureDescriptor("relative_power", "Relative power", "Spectral", "Band power normalized by total power.", True),
    FeatureDescriptor("median_frequency", "Median frequency", "Spectral", "Frequency dividing spectral power."),
    FeatureDescriptor("spectral_entropy", "Spectral entropy", "Spectral", "Spectral complexity estimate."),
    FeatureDescriptor("lempel_ziv_complexity", "Lempel-Ziv complexity", "Complexity", "Sequence complexity estimate."),
    FeatureDescriptor("ctm", "Central tendency measure", "Complexity", "Variability in phase space."),
    FeatureDescriptor("aec", "AEC", "Connectivity", "Amplitude envelope correlation."),
    FeatureDescriptor("orthogonalized_aec", "Orthogonalized AEC", "Connectivity", "Leakage-reduced AEC."),
    FeatureDescriptor("asc", "ASC", "Connectivity", "Amplitude squared correlation."),
    FeatureDescriptor("orthogonalized_asc", "Orthogonalized ASC", "Connectivity", "Leakage-reduced ASC."),
    FeatureDescriptor("pli", "PLI", "Connectivity", "Phase lag index."),
    FeatureDescriptor("wpli", "wPLI", "Connectivity", "Weighted phase lag index."),
    FeatureDescriptor("plv", "PLV", "Connectivity", "Phase locking value."),
]
