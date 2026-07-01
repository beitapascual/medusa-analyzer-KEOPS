import numpy as np
import random
from pathlib import Path
from medusa.core.data import BidsInfo, Recording, Signal, Channel, Sensor, ChannelSet, Events


def generate_medusa_bids_test_batch(out_dir="sample_data/medusa_source_records", n_subjects=20, n_sessions=3):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)

    # Duración aumentada a 5 segundos
    DURATION = 5.0

    for sub in range(1, n_subjects + 1):
        for ses in range(1, n_sessions + 1):
            sub_str = f"{sub:02d}"
            ses_str = f"{ses:02d}"

            # 1. Identidad de la grabación
            bids = BidsInfo(subject=sub_str, session=ses_str, task="gonogo", run=1)
            rec = Recording(bids)

            # ==========================================
            # 2. SEÑAL 1: Flujo EEG (Todos los sujetos)
            # ==========================================
            eeg_cs = ChannelSet()
            eeg_ch_names = ["Fp1", "Fp2", "F3", "F4", "C3", "C4", "P3", "P4"]

            # Se aplica GND tanto para reference como ground simulando un entorno reference-free
            eeg_cs.add_unipolar_eeg_channels(eeg_ch_names, reference="GND", ground="GND")

            # LÓGICA DE INYECCIÓN DE VARIABILIDAD (Para forzar la herencia)
            if sub <= 12:
                # GRUPO 1: Mayoría Global (60% del dataset) - Configuración actiCHamp Plus
                fs_eeg = 256.0
                manufacturer = "Brain Products"
                model = "actiCHamp Plus"
                ref = "GND"

                if sub == 1 and ses == 3: ref = "Fz"  # Excepción

            elif 13 <= sub <= 18:
                # GRUPO 2: Minoría Global / Mayoría por Sujeto
                fs_eeg = 500.0
                manufacturer = "Delsys"
                model = "Unknown"
                ref = "Mastoids"

                if ses == 3: fs_eeg = 1000.0  # Excepción

            else:
                # GRUPO 3: Aleatorio
                fs_eeg = random.choice([128.0, 256.0, 512.0])
                manufacturer = f"Brand_{random.randint(1, 10)}"
                model = f"Model_{random.randint(1, 5)}"
                ref = f"Ref_{random.randint(1, 5)}"

            n_samples_eeg = int(DURATION * fs_eeg)
            eeg_data = 20.0 * rng.standard_normal((n_samples_eeg, eeg_cs.n_channels))
            eeg_sig = Signal(eeg_data, fs=fs_eeg, channel_set=eeg_cs)

            rec.add_signal("eeg", eeg_sig)
            rec.set_sidecar("eeg",
                            Manufacturer=manufacturer,
                            ManufacturersModelName=model,
                            EEGReference=ref)

            # ==========================================
            # 3. SEÑAL 2: Flujo EMG (Solo para sujetos 1 a 10)
            # ==========================================
            if sub <= 10:
                emg_cs = ChannelSet()
                emg_cs.add_sensors([
                    Sensor("EMG_R_act", sensor_type="surface"), Sensor("EMG_R_ref", sensor_type="surface"),
                    Sensor("EMG_L_act", sensor_type="surface"), Sensor("EMG_L_ref", sensor_type="surface")
                ])
                emg_cs.add_channels(Channel("EMG_right", "EMG", "uV", sensor="EMG_R_act", reference="EMG_R_ref",
                                            reference_method="bipolar"))
                emg_cs.add_channels(Channel("EMG_left", "EMG", "uV", sensor="EMG_L_act", reference="EMG_L_ref",
                                            reference_method="bipolar"))

                fs_emg = 1000.0  # Típicamente mayor en EMG
                n_samples_emg = int(DURATION * fs_emg)
                emg_data = 50.0 * rng.standard_normal((n_samples_emg, emg_cs.n_channels))
                emg_sig = Signal(emg_data, fs=fs_emg, channel_set=emg_cs)

                rec.add_signal("emg", emg_sig)
                rec.set_sidecar("emg", Manufacturer="Delsys", PowerLineFrequency=50)

            # ==========================================
            # 4. EVENTOS (Todos los sujetos)
            # ==========================================
            events = Events(optional_columns={"trial_type": str, "value": int},
                            descriptions={"trial_type": "go or nogo", "value": "stimulus code"})

            # Tres eventos distribuidos a lo largo de los 5 segundos
            events.append([
                {"onset": 1.00, "duration": 0.20, "trial_type": "go", "value": 1},
                {"onset": 2.50, "duration": 0.20, "trial_type": "nogo", "value": 2},
                {"onset": 4.10, "duration": 0.20, "trial_type": "go", "value": 1}
            ])
            rec.set_events(events)

            # ==========================================
            # 5. METADATOS DEL PARADIGMA
            # ==========================================
            rec.set_experiment({
                "TaskInformation": {
                    "TaskName": "gonogo",
                    "TaskDescription": "Standard go/no-go task with 5 seconds duration",
                    "Instructions": "Press button when green, hold when red"
                }
            })

            # 6. Volcado al disco
            file_name = f"sub-{sub_str}_ses-{ses_str}_task-gonogo_recording.json"
            rec.save(str(out / file_name))

    print(f"Generados {n_subjects * n_sessions} registros multimodales MEDUSA en: {out_dir}")


if __name__ == "__main__":
    generate_medusa_bids_test_batch()