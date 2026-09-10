from medusa.core.legacy.recording import Recording as LegacyRecording
from medusa.core.legacy.convert import recorder_recording_to_v2
from pathlib import Path

files = list(Path(r"X:\Temps\braingym").rglob("*.bson"))

for file in files:
    print(files)
    mds_old = LegacyRecording.load(str(file))
    subject = str(file.parent.name).split('-')[1]
    mds_new = recorder_recording_to_v2(mds_old)
    mds_new.bids.subject = subject
    mds_new.save(rf'X:\Temps\braingym_new\sub-{mds_new.bids.subject}_task-{mds_new.bids.task}.json')