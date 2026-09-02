import numpy as np
import random
from pathlib import Path
from medusa.core.data import BidsInfo, Recording, Signal, Channel, Sensor, ChannelSet, Events


def generate_medusa_bids_test_batch(out_dir="bids_bd_pre_converter", n_subjects=20, n_sessions=3):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)

    # Duración mantenida en 300 segundos (5 minutos) para alojar eventos de larga duración
    DURATION = 300.0

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
                            descriptions={"trial_type": "event condition or type", "value": "stimulus code"})

            event_list = []

            # Bloque 1: Resting state inicial (Duración 60s)
            # Se aplica un jitter (variación aleatoria) per-sesión para que los onsets difieran ligeramente
            start_rest1 = 5.0 + rng.uniform(-0.5, 0.5)
            event_list.append({"onset": start_rest1, "duration": 60.0, "trial_type": "resting_state", "value": 10})

            # Estímulos auditivos superpuestos durante el resting state 1 (Instantáneos, duración 0)
            for offset in [10.0, 25.5, 42.0, 55.0]:
                sound_onset = start_rest1 + offset + rng.uniform(-0.2, 0.2)
                event_list.append({"onset": sound_onset, "duration": 0.0, "trial_type": "sound_stim", "value": 11})

            # Bloque 2: Instrucciones (Duración 10s)
            start_inst = 70.0 + rng.uniform(-0.5, 0.5)
            event_list.append({"onset": start_inst, "duration": 10.0, "trial_type": "instruction", "value": 20})

            # Bloque 3: Tarea Go/No-Go (Duración 60s)
            start_task1 = 85.0 + rng.uniform(-0.5, 0.5)
            event_list.append({"onset": start_task1, "duration": 60.0, "trial_type": "task_block", "value": 30})

            # Estímulos de la tarea superpuestos al bloque (Instantáneos)
            for i, offset in enumerate([5.0, 12.5, 23.0, 31.5, 45.0, 52.5]):
                stim_onset = start_task1 + offset + rng.uniform(-0.1, 0.1)
                ttype = "go" if i % 2 == 0 else "nogo"
                val = 1 if ttype == "go" else 2
                event_list.append({"onset": stim_onset, "duration": 0.0, "trial_type": ttype, "value": val})

            # Bloque 4: Resting state 2 (Duración 60s)
            start_rest2 = 160.0 + rng.uniform(-0.5, 0.5)
            event_list.append({"onset": start_rest2, "duration": 60.0, "trial_type": "resting_state", "value": 10})

            # Estímulos auditivos superpuestos durante el resting state 2
            for offset in [15.0, 30.0, 48.0]:
                sound_onset = start_rest2 + offset + rng.uniform(-0.2, 0.2)
                event_list.append({"onset": sound_onset, "duration": 0.0, "trial_type": "sound_stim", "value": 11})

            # Bloque 5: Tarea Go/No-Go 2 (Duración 60s)
            start_task2 = 230.0 + rng.uniform(-0.5, 0.5)
            event_list.append({"onset": start_task2, "duration": 60.0, "trial_type": "task_block", "value": 30})

            # Estímulos de la tarea 2 superpuestos
            for i, offset in enumerate([8.0, 15.0, 28.0, 35.0, 41.5, 50.0]):
                stim_onset = start_task2 + offset + rng.uniform(-0.1, 0.1)
                # Alternancia diferente para añadir variabilidad en los bloques
                ttype = "nogo" if i % 3 == 0 else "go"
                val = 2 if ttype == "nogo" else 1
                event_list.append({"onset": stim_onset, "duration": 0.0, "trial_type": ttype, "value": val})

            events.append(event_list)
            rec.set_events(events)

            # ==========================================
            # 5. METADATOS DEL PARADIGMA
            # ==========================================
            rec.set_experiment({
                "TaskInformation": {
                    "TaskName": "gonogo",
                    "TaskDescription": "Standard go/no-go task with overlapping blocks and resting states",
                    "Instructions": "Relax during resting state. Press button when green, hold when red during task."
                }
            })

            # 6. Volcado al disco
            file_name = f"sub-{sub_str}_ses-{ses_str}_task-gonogo_rec.json"
            rec.save(str(out / file_name))

    print(f"Generados {n_subjects * n_sessions} registros multimodales MEDUSA en: {out_dir}")


if __name__ == "__main__":
    generate_medusa_bids_test_batch()