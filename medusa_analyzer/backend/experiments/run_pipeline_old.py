import numpy as np
from copy import deepcopy

from scipy.stats import kurtosis, skew
from scipy.io import savemat
import csv
from pathlib import Path
import json

from medusa.core.data.recording import Recording
from medusa.signal import frequency_filtering, spatial_filtering, artifact_removal, segmentation
import pandas as pd

def run_pipeline(state):
    """
    Main pipeline function of the eeg features extraction that executes preprocessing, segmentation, and parameter
    computation for all selected files based on the provided configuration.
    """

    # Get the selected files and associated variables
    selected_recordings = state['selected_recordings']
    total_files = len(selected_recordings)
    error_found = False

    # Store the bands if band segmentation is enabled, otherwise use broadband
    bands = state['preprocessing']['selected_frequency_bands']
    # Sorted bands to have broadband in the first position
    bands = sorted(bands, key=lambda b: 0 if b['title'].lower() == 'broadband' else 1)

    # To store rejection summary and execution logs
    rejection_summary = []
    execution_logs = []

    # Loop through each selected file
    for idx_file, file in enumerate(selected_recordings):
        try:

            #0 Load data
            data = build_recording(file['path'])
            datatype = file['datatype']
            subj_id = file['path'].split('\\')

            # Get information from recording
            raw_signal = data.data[datatype].signal
            times = data.data[datatype].times
            fs = data.data[datatype].fs
            n_cha = data.data[datatype].channel_set.n_channels
            channs = data.data[datatype].channel_set.labels
            # Events
            base_name = Path(file['path']).name.rsplit('_', 1)[0]
            events_path = Path(file['path']).parent.parent /  f"{base_name}_events.tsv"
            events = pd.read_table(events_path)

            # Ensure consistent sampling frequency
            if fs != state['metadata']['sampling_frequency']:
                raise Exception(
                    f"[{file}] Does not have the sampling frequency of the selected pipeline."
                    f"Expected {state['metadata']['sampling_frequency']}, but got {fs}.")

            ## First step: Preprocessing
            processed_signal = raw_signal.copy()
            if state['preprocessing']['car'] \
                    or any(filtro['enabled'] for filtro in state['preprocessing']['filters'].values()):
                processed_signal = apply_preprocessing(processed_signal, fs, state['preprocessing'])

            ## Second step: Get indices of the thresholding
            if state['segmentation']["thresholding"]['enabled']:

                epochs = segment_signal(processed_signal, times, fs, events, state)

                # Get the thresholding parameters
                thres_k = state['segmentation']['sigma']
                thres_samples = state['segmentation']["samples"]
                thres_channels = state['segmentation']["channels"]
                prc_rejected = dict()
                idx_reject = dict()
                for base_evt, epochs_base in epochs.items():
                    for evt, epochs_base_evt in epochs_base.items():
                        # Get the indices of rejected epochs
                        thres_mean = np.nanmean(np.nanmean(epochs_base_evt, axis=1), axis=0)
                        thres_std = np.nanmean(np.nanstd(epochs_base_evt, axis=1), axis=0)
                        prc_rejected[base_evt][evt], _, idx_reject[base_evt][evt] = artifact_removal.reject_noisy_segments(
                            epochs_base_evt, thres_mean, thres_std, k=thres_k, n_samp=thres_samples, n_channels=thres_channels)

                        # Store rejection summary
                        prc_rejected_tmp = np.round(prc_rejected[base_evt][evt], 2)
                        n_rejected = int((prc_rejected_tmp * epochs[base_evt][evt].shape[0]) / 100)
                        rejection_summary.append({
                            'subject': subj_id,
                            'prc_rejected': prc_rejected_tmp,
                            'n_rejected': n_rejected,
                            'base_event': base_evt,
                            'event': evt
                        })

                del epochs  # Free memory

            # # Update the progress bar and labels
            # global_progress = (i * steps_per_file + 3) / total_steps * 100
            # self.progress.emit(int(global_progress))

            ## Third step: Band segmentation
            # For each band...
            for j, band in enumerate(bands):
                # Band info
                band_name = band['title']
                low_cut, high_cut = band['low_cut'], band['high_cut']

                # Workaround to allow filtering in the Nyquist frequency
                if high_cut == fs/2:
                    high_cut -= 1e-6

                # If the band is not broadband, apply band filtering (the broadband does not require filtering)
                if band_name.lower() != 'broadband':
                    order = 1000 if state['preprocessing']['bandpass'] is False else state['preprocessing']['filters']['bandpass']

                    processed_signal_band = (frequency_filtering.FIRFilter(
                        state['preprocessing']['filters']['bandpass']['order'], [low_cut, high_cut],
                        'bandpass', window=state['preprocessing']['filters']['bandpass']['window'])
                                             .fit_transform(processed_signal.copy(), fs))
                else:
                    processed_signal_band = processed_signal.copy()

                # # Update the progress bar and labels
                # global_progress = (i * steps_per_file + 3 + j * steps_per_band + 1) / total_steps * 100
                # self.progress.emit(int(global_progress))

                # Deepcopy the data to avoid modifying the original data object
                save_outputs(
                    build_output_dict(processed_signal_band, times, channs, fs),
                    file, band_name, None, 'preprocessed', state
                )

                ## Fourth step: Segmentation
                epochs = segment_signal(processed_signal, times, fs, events, state)

                for base_evt, epochs_base in epochs.items():
                    for evt, epochs_base_evt in epochs_base.items():

                        # # Update the progress bar and labels
                        # global_progress = (
                        #                               i * steps_per_file + 3 + j * steps_per_band + 1 + k * steps_per_cond + 1) / total_steps * 100
                        # self.progress.emit(int(global_progress))

                        ## Fifth step: Apply thresholding rejection if enabled
                        if state['segmentation']["thresholding"]:
                            # If all the epochs are rejected, skip this condition
                            if all(idx_threshold[cond]):
                                _log_with_store(
                                    f"⚠️ All epochs corresponding to condition '{cond}' in file '{file}' have been rejected. Skipping.",
                                    'warning')
                                continue

                            # Remove the rejected epochs from the epochs array
                            epochs = np.delete(epochs, idx_threshold[cond], axis=0)
                            # Also remove the discarded epochs from idx_events if segmentation type is 'event'
                            if settings_dic['segmentation']['segmentation_type'] == 'event':
                                idx_events = np.delete(idx_events, idx_threshold[cond], axis=0)

                        # Update the progress bar and labels
                        global_progress = (
                                                      i * steps_per_file + 3 + j * steps_per_band + 1 + k * steps_per_cond + 2) / total_steps * 100
                        self.progress.emit(int(global_progress))

                        ## Sixth step: Apply resampling if enabled
                        if epochs is not None and settings_dic['segmentation']['resample']:
                            resample_fs = settings_dic['segmentation']['resample_fs']
                            window = [0, (epochs.shape[1] / fs) * 1000]  # Window in ms
                            epochs = medusa.resample_epochs(epochs, window, resample_fs)

                        # Update the progress bar and labels
                        global_progress = (
                                                      i * steps_per_file + 3 + j * steps_per_band + 1 + k * steps_per_cond + 3) / total_steps * 100
                        self.progress.emit(int(global_progress))

                        # Save the segmented signals (if required), separately for each condition (and event, if selected)
                        if settings_dic['segmentation']['segmentation_type'] == 'condition':
                            save_outputs(self, deepcopy(epochs), base_name, band_name, cond, None, 'seg',
                                         settings_dic['save'])
                        elif settings_dic['segmentation']['segmentation_type'] == 'event':
                            for evt in np.unique(idx_events):
                                # Get the epochs corresponding to the current event
                                current_epochs = epochs[(idx_events.ravel() == evt), :, :]
                                # Get the event name from its label
                                event_name = None
                                for key, info in signal_marks.app_settings['events'].items():
                                    if info['label'] == evt:
                                        event_name = key
                                        break
                                save_outputs(self, deepcopy(current_epochs), base_name, band_name, cond, event_name,
                                             'seg', settings_dic['save'])

                        if n_cha == 1:
                            epochs = epochs[:, :, None]

                        ## Seventh step: Parameter computation
                        if settings_dic['segmentation']['segmentation_type'] == 'condition':
                            params = compute_parameters(epochs, fs, band, settings_dic)
                            save_outputs(self, deepcopy(params), base_name, band_name, cond, None, 'param',
                                         settings_dic['save'])
                        elif settings_dic['segmentation']['segmentation_type'] == 'event':
                            for evt in np.unique(idx_events):
                                # Get the epochs corresponding to the current event
                                current_epochs = epochs[(idx_events.ravel() == evt), :, :]
                                current_params = compute_parameters(current_epochs, fs, band, settings_dic)
                                # Get the event name from its label
                                event_name = None
                                for key, info in signal_marks.app_settings['events'].items():
                                    if info['label'] == evt:
                                        event_name = key
                                        break
                                save_outputs(self, deepcopy(current_params), base_name, band_name, cond, event_name,
                                             'param', settings_dic['save'])
                    # Update the progress bar and labels
                    global_progress = (
                                                  i * steps_per_file + 3 + j * steps_per_band + 1 + k * steps_per_cond + 7) / total_steps * 100
                    self.progress.emit(int(global_progress))

        # Exception handling
        except Exception as e:
            a = 0
            # error_found = True
            # print(f"Error preprocessing {file}: {e}", 'error')
            # self.text_progress.emit("Error")

    # Save logs and summary
    try:
        selected_folder = Path(settings_dic['save']["folder"])
        derivatives_path = selected_folder / "derivatives"
        derivatives_path.mkdir(exist_ok=True)

        # Save rejection summary to CSV
        if rejection_summary:
            csv_path = derivatives_path / "rejection_summary.csv"
            with open(csv_path, mode='w', newline='') as csv_file:
                fieldnames = ['subject', 'condition', 'prc_rejected', 'n_rejected']
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                for row in rejection_summary:
                    writer.writerow(row)
                row = {
                    'subject': f"K STDs: {settings_dic['segmentation']['thres_k']}",
                    'condition': f"Samples: {settings_dic['segmentation']['thres_samples']}",
                    'prc_rejected': f"N Channels: {settings_dic['segmentation']['thres_channels']}"
                }
                writer.writerow(row)
            self.log.emit(f"✅ Rejection summary saved to {csv_path}", "")

        # Save execution warnings/errors to TXT
        if execution_logs:
            log_path = derivatives_path / "error_log.txt"
            with open(log_path, mode='w', encoding='utf-8') as txt_file:
                for log_entry in execution_logs:
                    txt_file.write(log_entry + "\n")
            self.log.emit(f"✅ Execution logs saved to {log_path}", "")

    except Exception as e:
        self.log.emit(f"⚠️ Could not save logs/summary: {e}", "warning")

    self.text_progress.emit("Completed")

    return error_found


#################### HELPER FUNCTIONS

def build_recording(path):
    from medusa.core.data import Recording, Signal, ChannelSet, BidsInfo

    with open(path) as json_data:
        data = json.load(json_data)
        json_data.close()

    rec = Recording(BidsInfo(
        subject="dummy", session="dummy", task="dummy", run=1,
        participant={"age": 00, "sex": "F", "handedness": "right"}))
    cs = ChannelSet()
    cs.add_unipolar_eeg_channels(
        data['channels'],
        reference="DummyRef", ground="DummyGnd")
    sig = Signal(data['signal'],
                     fs=data['fs'], channel_set=cs)
    rec.add_signal("eeg", sig)

    return rec

def build_output_dict(signal, times, ch_names, fs):
    output_dic = {
        "fs": fs,
        "channels": ch_names,
        "times": times,
        "signal": signal
    }
    return output_dic

def segment_signal(signal, times, fs, events, state, norm = None):

    epochs = dict()
    # For each condition selected...
    for base_evt in state['segmentation']['event_groups']:

        if base_evt['base_event'] == None:
            base_evt['base_event'] = 'full_recording'

        current_base_evt = events[events['trial_type'] == base_evt['base_event']]

        for row in current_base_evt.itertuples(index=False):
            start_idx = np.searchsorted(times, row.onset)
            end_idx = np.searchsorted(times, row.onset + row.duration)
            signal_base = signal[:, start_idx:end_idx]
            times_base = times[:, start_idx:end_idx]

            segmentation_strategy = state['segmentation'].get('segmentation_strategy', 'window-based')

            # If segmentation type is 'condition'
            if base_evt['duration_events']:
                if segmentation_strategy in {'onset', 'onset-based'}:
                    onset_epoch = state['segmentation']['epoch_parameters']['instant_events']
                    epoch_window = [onset_epoch['start'], onset_epoch['end']]
                    baseline = [onset_epoch['baseline_start'], onset_epoch['baseline_end']]

                    for evt in base_evt['duration_events']:
                        current_evts = events[events['trial_type'] == evt]

                        try:
                            epochs_tmp = segmentation.segment_signal_around_events(
                                times_base,
                                signal_base,
                                current_evts.onset,
                                fs,
                                epoch_window,
                                baseline,
                                norm=norm,
                            )
                        except KeyError:
                            continue
                        if epochs_tmp is not None:
                            epochs[base_evt['base_event']][evt](epochs_tmp)
                            del epochs_tmp
                    continue

                segment_length = state['segmentation']['epoch_parameters']['duration_events']['duration_epoch_length_ms']
                stride = state['segmentation']['epoch_parameters']['duration_events']['stride_percent']

                for evt in base_evt['duration_events']:
                    current_evts = events[events['trial_type'] == evt]

                    for row in current_evts.itertuples(index=False):
                        start_idx = np.searchsorted(times_base, row.onset)
                        end_idx = np.searchsorted(times_base, row.onset + row.duration)
                        # Validar que los índices están dentro del rango y forman un segmento válido
                        if start_idx >= len(times_base) or end_idx > len(times_base):
                            continue  # Ignorar esta iteración y pasar al siguiente evento

                        signal_evt = signal_base[:, start_idx:end_idx]

                        # Get epochs for the current condition
                        epochs_tmp = segmentation.segment_signal(
                            signal_evt, segment_length, stride, norm=norm)

                        if epochs_tmp is not None:
                            epochs[base_evt['base_event']][evt](epochs_tmp)
                            del epochs_tmp

            elif base_evt['instant_events']:
                onset_epoch = state['segmentation']['epoch_parameters']['instant_events']
                epoch_window = [onset_epoch['start'], onset_epoch['end']]
                baseline = [onset_epoch['baseline_start'], onset_epoch['baseline_end']]

                for evt in base_evt['instant_events']:
                    current_evts = events[events['trial_type'] == evt]

                    try:
                        epochs_tmp = segmentation.segment_signal_around_events(times_base, signal_base, current_evts.onset, fs,
                                                                               epoch_window,
                                                                               baseline,
                                                                               norm=norm)
                    except KeyError:
                        continue
                    if epochs_tmp is not None:
                        epochs[base_evt['base_event']][evt](epochs_tmp)
                        del epochs_tmp

    # # If no epochs were found for this condition, skip it
    # if len(epochs) == 0:
    #     print(f"⚠️ No valid epochs for '{cond}' in file '{file}'. Skipping.", 'warning')
    #     continue

    return epochs




def _get_event_indices_in_range(marks, event_key, start_time, end_time):
    """
    Return indices of events that occur within a given time interval.
    """
    events_labels = np.array(marks.events_labels)
    events_times = np.array(marks.events_times)
    return np.where(
        (events_labels == event_key) &
        (events_times >= start_time) &
        (events_times <= end_time))[0]


def save_outputs(data, file, band_name, cond, key, state):
    """
    Guarda los resultados del pipeline en estructura semi-BIDS dentro de /derivatives.

    Estructura:
    derivatives/
        ├── preprocessed/
        ├── segmented/
        └── parameters/
    """
    selected_folder = Path(state["output_derivatives_path"])
    selected_folder.mkdir(exist_ok=True)

    # Obtener info del sujeto y sesión desde el nombre del archivo base
    filename = file['relative_path']
    # --- Saving preprocessed signals (.rec.bson) ---
    if key == "preprocessed":
        output_path = selected_folder / "preprocessed" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path = output_path.with_stem(f"{output_path.stem}_band-{band_name.replace('-', '')}")

        signal_export = {
            "fs": data['fs'],
            "channels": data['ch_names'],
            "times": data['times'],
            "signal": data['signal']
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(signal_export, f)

        # worker.log.emit(f"✅ Preprocessed saved: {output_path}", "")

    # --- Saving segmented signals (.mat) ---
    if key == "seg" and settings_dic["save_segmented"]:
        if ses_id:
            seg_dir = derivatives_path / "segmented" / subj_id / ses_id / "EEG"
        else:
            seg_dir = derivatives_path / "segmented" / subj_id / "EEG"
        seg_dir.mkdir(parents=True, exist_ok=True)

        if event is not None:
            output_name = f"{base_stem}_band-{band_name.replace('-', '')}_cond-{cond.replace('-', '')}_event-{event.replace('-', '')}.mat"
        else:
            output_name = f"{base_stem}_band-{band_name.replace('-', '')}_cond-{cond.replace('-', '')}.mat"
        output_path = seg_dir / output_name

        savemat(output_path, {'epochs': data})
        worker.log.emit(f"✅ Segmented saved: {output_path}", "")

    # --- Saving parameters (.mat) ---
    if key == "param" and settings_dic["save_params"]:
        if ses_id:
            param_dir = derivatives_path / "parameters" / subj_id / ses_id / "EEG"
        else:
            param_dir = derivatives_path / "parameters" / subj_id / "EEG"
        param_dir.mkdir(parents=True, exist_ok=True)

        if not isinstance(data, dict):
            if event is not None:
                outname = f"{subj_id}_param-unknown_band-{band_name.replace('-', '')}_cond-{cond.replace('-', '')}_event-{event.replace('-', '')}.mat"
            else:
                outname = f"{subj_id}_param-unknown_band-{band_name.replace('-', '')}_cond-{cond.replace('-', '')}.mat"
            outpath = param_dir / outname
            savemat(outpath, {'parameters': data})
            worker.log.emit(f"⚠️ Parameters: saved fallback file {outpath}", "")
            return

        params_dict = dict(data)

        # 1) PSDs: (psd_<band> + psd_freqs_<band>)
        psd_bands = set()
        for k in list(params_dict.keys()):
            if k.startswith('psd_'):
                psd_bands.add(k[4:])
            if k.startswith('psdfreqs_'):
                psd_bands.add(k[10:])

        for b in psd_bands:
            psd_key = f'psd{b}'
            freqs_key = f'psdfreqs{b}'
            psd_val = params_dict.pop(psd_key, None)
            freqs_val = params_dict.pop(freqs_key, None)

            metric_label = (f"psd{b}")
            if event is not None:
                outname = f"{base_stem}_param-{metric_label.replace('-', '')}_band-{band_name.replace('-', '')}_cond-{cond.replace('-', '')}_event-{event.replace('-', '')}.mat"
            else:
                outname = f"{base_stem}_param-{metric_label.replace('-', '')}_band-{band_name.replace('-', '')}_cond-{cond.replace('-', '')}.mat"
            outpath = param_dir / outname

            save_struct = {}
            if psd_val is not None:
                save_struct['psd'] = np.asarray(psd_val)
            if freqs_val is not None:
                save_struct['freqs'] = np.asarray(freqs_val)

            mat_dict = {metric_label: save_struct}

            savemat(outpath, mat_dict)
            worker.log.emit(f"✅ Parameter saved: {outpath}", "")

        # 2) Other parameters
        for k, v in list(params_dict.items()):
            metric_label = k.replace('_', '-')

            if event is not None:
                outname = f"{base_stem}_param-{metric_label.replace('-', '')}_band-{band_name}_cond-{cond}_event-{event.replace('-', '')}.mat"
            else:
                outname = f"{base_stem}_param-{metric_label.replace('-', '')}_band-{band_name.replace('-', '')}_cond-{cond.replace('-', '')}.mat"
            outpath = param_dir / outname

            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) and 'band' in v[0]:
                for entry in v:
                    bname = entry.get('band', 'unknown')
                    val = np.asarray(entry.get('value'))

                    # Nombre del archivo: usa la banda del diccionario, NO la del argumento
                    if event is not None:
                        outname = (
                            f"{base_stem}_param-{metric_label.replace('-', '')}_band-{bname.replace('-', '')}"
                            f"_cond-{cond.replace('-', '')}_event-{event.replace('-', '')}.mat"
                        )
                    else:
                        outname = (
                            f"{base_stem}_param-{metric_label.replace('-', '')}_band-{bname.replace('-', '')}"
                            f"_cond-{cond.replace('-', '')}.mat"
                        )

                    outpath = param_dir / outname
                    savemat(outpath, {
                        "param": val,
                        "info": metric_label
                    })
                    worker.log.emit(f"✅ Parameter saved: {outpath}", "")

            elif isinstance(v, dict):
                nested = {}
                for kk, vv in v.items():
                    nested[kk] = np.asarray(vv)

                savemat(outpath, {
                    "param": nested,
                    "info": metric_label
                })
            else:
                try:
                    savemat(outpath, {
                        "param": np.asarray(v),
                        "info": metric_label
                    })
                except Exception:
                    savemat(outpath, {
                        "param": np.asarray(v, dtype=object),
                        "info": metric_label
                    })

            worker.log.emit(f"✅ Parameter saved: {outpath}", "")


#################### PREPROCESSING

def apply_preprocessing(signal, fs, cfg):
    """
    Apply bandpass, notch filtering, and Common Average Reference (CAR).
    """
    # Bandpass filter
    for filter in cfg['preprocessing']['filters']:
        if filter['filter_type'] == 'fir':
            signal = frequency_filtering.FIRFilter(filter['order'], [filter['low_cut'], filter['high_cut']], filter['type'],
                                      window=filter['window']).fit_transform(signal, fs)
        else:
            signal = frequency_filtering.IIRFilter(filter['fir_order'], [filter['low_cut'], filter['high_cut']], filter['type'],
                                      filt_method='sosfiltfilt').fit_transform(signal, fs)

    # CAR and return
    return spatial_filtering.car(signal) if cfg['car'] else signal


##################### BAND FILTERING

def band_filtering(signal, bp_min, bp_max, fs, cfg):
    """
    Apply band segmentation with a FIR bandpass filter. Used when preprocessing is disabled but band-specific
    segmentation is required.
    """
    order = 1000 if cfg['bandpass'] is False else cfg['bp_order']
    win = 'hamming' if cfg['bandpass'] is False else cfg['bp_win']
    bp_filter = medusa.FIRFilter(order, [bp_min, bp_max], 'bandpass', window=win)
    signal = bp_filter.fit_transform(signal, fs)
    return signal


##################### BAND FILTERING

def compute_parameters(epochs, fs, band, cfg):
    # Initialize dict that will contain all the computed parameters
    params = {}

    ## BASIC STATISTICAL PARAMETERS
    stat_funcs = {
        'mean': np.mean,
        'variance': np.var,
        'median': np.median,
        'kurtosis': kurtosis,
        'skewness': skew
    }
    # Account if only one (2D array) or multiple epoch are present (3D array)
    axis = 0 if epochs.ndim == 2 else 1
    # For each parameter...
    for name, func in stat_funcs.items():
        # If selected...
        if cfg['parameters'][name]:
            # Compute it
            val = func(epochs, axis=axis)
            # Average across epochs if required and if multiple epochs are present
            val = np.mean(val, axis=0) if cfg['segmentation']['average'] and epochs.ndim == 3 else val
            # Store in the params dict
            params[f"{name}"] = val

    ## POWER SPECTRAL DENSITY (PSD)
    # PSD would be computed if explicitly selected
    explicit_psd = cfg['parameters']['psd']
    # Or if any parameter that depends on it is selected
    params_require_psd = any([cfg['parameters'][spec_param]
                              for spec_param in
                              ['absolute_power', 'median_frequency', 'spectral_entropy', 'relative_power']])
    require_psd = explicit_psd or params_require_psd

    if require_psd:
        # Use user-defined parameters for segmenting and windowing
        segment_psd = cfg['parameters']['psd_segment_pct']
        overlap_psd = cfg['parameters']['psd_overlap_pct']
        window_psd = cfg['parameters']['psd_window']

        # Compute PSD using specified segment and window settings
        fxx, psd = medusa.transforms.power_spectral_density(epochs, fs, segment_psd, overlap_psd, window_psd)

        # Store PSD values: average across trials if averaging is enabled
        try:
            psd_values = np.nanmean(psd, axis=0) if cfg['segmentation']['average'] and epochs.ndim == 3 else psd
            params['psd'] = {
                'values': psd_values,
                'freqs': fxx
            }
        except Exception as e:
            print(e)

    ## SPECTRAL METRICS - RELATIVE POWER
    # Only compute the RP in the broadband, and if explicitly selected
    if band['name'] == 'broadband' and cfg['parameters']['relative_power']:
        val = []

        # The bands will be different if band segmentation is enabled or not
        if cfg['preprocessing']['band_segmentation']:
            selected_bands = cfg['preprocessing']['selected_bands']
        else:
            selected_bands = cfg['parameters']['selected_rp_bands']

        # # Define broadband range, as the minimum of the mins and the maximum of the maxs of the selected bands
        # min_val = min(band["min"] for band in selected_bands if band["name"] != 'broadband')
        # max_val = max(band["max"] for band in selected_bands if band["name"] != 'broadband')
        # Define broadband range based on the broadband limits
        min_val = band[
            'min']  # Now band is broadband (condition above), so we can use its min and max values to define the range
        max_val = band['max']

        # Loop through each selected band
        for band_rp in selected_bands:
            if band_rp["name"] != 'broadband':
                # Define band parameters
                band_range = [band_rp["min"], band_rp["max"]]
                # Compute the metric
                val_band = medusa.signal_metrics.band_power.band_power(psd, fs, band_range, 'relative',
                                                                       [min_val, max_val])
                # Average across epochs if required and if multiple epochs are present
                val_band = np.nanmean(val_band, axis=0) if cfg['segmentation'][
                                                               'average'] and epochs.ndim == 3 else val_band
                val.append({"band": band_rp["name"], "value": val_band})

            params[f"relative_power"] = val

    ## SPECTRAL METRICS - OTHERS
    spectral_funcs = {
        "absolute_power": medusa.signal_metrics.band_power.band_power,
        "median_frequency": medusa.signal_metrics.median_frequency.median_frequency,
        "spectral_entropy": medusa.signal_metrics.shannon_spectral_entropy.shannon_spectral_entropy,
    }

    # For each parameter...
    for name, func in spectral_funcs.items():
        # If selected...
        if cfg['parameters'][name]:
            # Get the current band range
            band_range = [band['min'], band['max']]
            # Compute the metric
            if name == 'absolute_power':
                val = func(psd, fs, band_range, 'absolute')
            else:
                val = func(psd, fs, band_range)
            # Average across epochs if required and if multiple epochs are present
            val = np.nanmean(val, axis=0) if cfg['segmentation']['average'] and epochs.ndim == 3 else val
            # Store in the params dict
            params[f"{name}"] = val

    ## NONLINEAR METRICS
    nonlinear_funcs = {
        'ctm': lambda: medusa.signal_metrics.central_tendency.central_tendency_measure(epochs,
                                                                                       cfg['parameters']['ctm_r']),
        'sample_entropy': lambda: medusa.signal_metrics.sample_entropy.sample_entropy(epochs,
                                                                                      cfg['parameters'][
                                                                                          'sample_entropy_m'],
                                                                                      cfg['parameters'][
                                                                                          'sample_entropy_r']),
        'multiscale_sample_entropy': lambda: medusa.signal_metrics.multiscale_entropy.multiscale_entropy(
            epochs, cfg['parameters']['multiscale_sample_entropy_scale'],
            cfg['parameters']['multiscale_sample_entropy_m'],
            cfg['parameters']['multiscale_sample_entropy_r']),
        'lzc': lambda: medusa.signal_metrics.lempelziv_complexity.lempelziv_complexity(epochs),
        'multiscale_lzc': lambda: medusa.signal_metrics.multiscale_lempelziv_complexity.multiscale_lempelziv_complexity(
            epochs, cfg['parameters']['multiscale_lzc_scales'])}

    # For each parameter...
    for name, func in nonlinear_funcs.items():
        # If selected...
        if cfg['parameters'][name]:
            # Compute it
            val = func()
            # Average across epochs if required and if multiple epochs are present
            val = np.nanmean(val, axis=0) if cfg['segmentation']['average'] and epochs.ndim == 3 else val
            params[f"{name}"] = val

    ## CONNECTIVITY METRICS
    connectivity_funcs = {
        'iac': lambda: medusa.connectivity_metrics.iac(epochs, cfg['parameters']['ort_iac']),
        'aec': lambda: medusa.connectivity_metrics.aec(epochs, cfg['parameters']['ort_aec']),
        'plv': lambda: medusa.connectivity_metrics.plv(epochs),
        'pli': lambda: medusa.connectivity_metrics.pli(epochs),
        'wpli': lambda: medusa.connectivity_metrics.wpli(epochs),
    }

    # For each parameter...
    for name, func in connectivity_funcs.items():
        # If selected...
        if cfg['parameters'][name]:
            # Compute it
            val = func()
            # Average across epochs if required and if multiple epochs are present
            val = np.nanmean(val, axis=0) if cfg['segmentation']['average'] and epochs.ndim == 3 else val
            params[f"{name}"] = val

    return params


def load_config(files_widget, data):
    # BIOSIGNAL INFO
    biosignal_txt = files_widget.biosignalBox.currentText()
    biosignal = biosignal_txt.split(" ")[1]
    files_widget.controller.biosignal_info = files_widget.controller.biosignals[biosignal]

    # PREPROCESSING
    prep_cfg = data["preprocessing"]
    idx_preprocessing_widget = next(
        (i for i, d in enumerate(files_widget.main_window.controller.experiment['pipeline']) if
         d.get('widget') == "PreprocessingWidget"))
    preproc_widget = files_widget.main_window.stackedWidget.widget(
        idx_preprocessing_widget)  # widget(2) is the preprocessing widget
    preproc_widget.minbroadBox.setValue(prep_cfg['broadband_min'])
    preproc_widget.maxbroadBox.setValue(prep_cfg['broadband_max'])
    preproc_widget.preprocessingButton.setChecked(bool(prep_cfg["apply_preprocessing"]))
    preproc_widget.notchCBox.setChecked(bool(prep_cfg['notch']))
    preproc_widget.minfreqnotchBox.setValue(
        prep_cfg['notch_min'] if prep_cfg['notch_min'] is not None else preproc_widget.defaults["minfreqnotch"])
    preproc_widget.maxfreqnotchBox.setValue(
        prep_cfg['notch_max'] if prep_cfg['notch_max'] is not None else preproc_widget.defaults["minfreqnotch"])
    preproc_widget.orderNotchBox.setValue(
        prep_cfg['notch_order'] if prep_cfg['notch_order'] is not None else preproc_widget.defaults["ordernotch"])
    preproc_widget.winnotchBox.setCurrentText(prep_cfg['notch_win'])
    preproc_widget.bpCBox.setChecked(bool(prep_cfg['bandpass']))
    preproc_widget.minfreqbpBox.setValue(
        prep_cfg['bp_min'] if prep_cfg['bp_min'] is not None else preproc_widget.defaults["minfreqbp"])
    preproc_widget.maxfreqbpBox.setValue(
        prep_cfg['bp_max'] if prep_cfg['bp_max'] is not None else preproc_widget.defaults["maxfreqbp"])
    preproc_widget.orderbpBox.setValue(
        prep_cfg['bp_order'] if prep_cfg['bp_order'] is not None else preproc_widget.defaults["orderbp"])
    preproc_widget.winbpBox.setCurrentText(prep_cfg['bp_win'])
    preproc_widget.carCBox.setChecked(bool(prep_cfg['car']))
    preproc_widget.bandCBox.setChecked(bool(prep_cfg['band_segmentation']))
    bands_list = prep_cfg.get("selected_bands") or []
    bands = bands_list[1:] if len(bands_list) > 1 else []  # Exclude 'broadband' if other bands are present
    if bands:
        preproc_widget.controller.update_band_label("segmentation", bands)
    # Store
    files_widget.main_window.controller.preproc_config = prep_cfg

    # SEGMENTATION
    segm_cfg = data["segmentation"]
    idx_segmentation_widget = next(
        (i for i, d in enumerate(files_widget.main_window.controller.experiment['pipeline']) if
         d.get('widget') == "SegmentationWidget"))
    segm_widget = files_widget.main_window.stackedWidget.widget(
        idx_segmentation_widget)  # widget(3) is the segmentation widget
    segm_widget.conditionRButton.setChecked(
        segm_cfg['segmentation_type'] == 'condition')  # RButton, so it is exclusive with eventRButton
    segm_widget.trialBox.setValue(
        segm_cfg['trial_length'] if segm_cfg['trial_length'] is not None else segm_widget.defaults['triallength'])
    segm_widget.trialstrideBox.setValue(
        segm_cfg['trial_stride'] if segm_cfg['trial_stride'] is not None else segm_widget.defaults['trialstride'])
    segm_widget.winBox_1.setValue(
        segm_cfg['window_start'] if segm_cfg['window_start'] is not None else segm_widget.defaults['windowbox1'])
    segm_widget.winBox_2.setValue(
        segm_cfg['window_end'] if segm_cfg['window_end'] is not None else segm_widget.defaults['windowbox2'])
    segm_widget.normCBox.setChecked(bool(segm_cfg['norm']))
    if segm_cfg['norm_type'] == 'z':
        segm_widget.zscoreRButton.setChecked(True)  # RButton, so it is exclusive with dcRButton
    segm_widget.baselineCBox_1.setValue(
        segm_cfg['baseline_start'] if segm_cfg['baseline_start'] is not None else segm_widget.defaults['baselinewin1'])
    segm_widget.baselineCBox_2.setValue(
        segm_cfg['baseline_end'] if segm_cfg['baseline_end'] is not None else segm_widget.defaults['baselinewin2'])
    segm_widget.averageCBox.setChecked(bool(segm_cfg['average']))
    segm_widget.thresCBox.setChecked(bool(segm_cfg['thresholding']))
    segm_widget.threskBox.setValue(
        segm_cfg['thres_k'] if segm_cfg['thres_k'] is not None else segm_widget.defaults['threshold'])
    segm_widget.thressampBox.setValue(
        segm_cfg['thres_samples'] if segm_cfg['thres_samples'] is not None else segm_widget.defaults['thressamples'])
    segm_widget.threschanBox.setValue(
        segm_cfg['thres_channels'] if segm_cfg['thres_channels'] is not None else segm_widget.defaults['threschannels'])
    segm_widget.resampleCBox.setChecked(bool(segm_cfg['resample']))
    segm_widget.resamplefsBox.setValue(
        segm_cfg['resample_fs'] if segm_cfg['resample_fs'] is not None else segm_widget.defaults['resamplefs'])
    # Store
    files_widget.main_window.controller.segmentation_config = segm_cfg

    # PARAMETERS
    params_cfg = data["parameters"]
    idx_parameters_widget = next((i for i, d in enumerate(files_widget.main_window.controller.experiment['pipeline']) if
                                  d.get('widget') == "ParametersWidget"))
    params_widget = files_widget.main_window.stackedWidget.widget(
        idx_parameters_widget)  # widget(4) is the parameters widget
    params_widget.meanCBox.setChecked(bool(params_cfg['mean']))
    params_widget.medianCBox.setChecked(bool(params_cfg['median']))
    params_widget.varianceCBox.setChecked(bool(params_cfg['variance']))
    params_widget.kurtosisCBox.setChecked(bool(params_cfg['kurtosis']))
    params_widget.skewnessCBox.setChecked(bool(params_cfg['skewness']))
    params_widget.psdCBox.setChecked(bool(params_cfg['psd']))
    params_widget.segmentpsdBox.setValue(
        params_cfg['psd_segment_pct'] if params_cfg['psd_segment_pct'] is not None else params_widget.defaults[
            'psdsegment'])
    params_widget.overlappsdBox.setValue(
        params_cfg['psd_overlap_pct'] if params_cfg['psd_overlap_pct'] is not None else params_widget.defaults[
            'psdoverlap'])
    params_widget.psdcomboBox.setCurrentText(params_cfg['psd_window'])
    params_widget.controller.loading_config = True
    params_widget.rpCBox.setChecked(bool(params_cfg['relative_power']))
    params_widget.controller.update_band_label('rp', params_cfg["selected_rp_bands"])
    params_widget.controller.loading_config = False
    params_widget.apCBox.setChecked(bool(params_cfg['absolute_power']))
    params_widget.mfCBox.setChecked(bool(params_cfg['median_frequency']))
    params_widget.seCBox.setChecked(bool(params_cfg['spectral_entropy']))
    params_widget.ctmCBox.setChecked(bool(params_cfg['ctm']))
    params_widget.ctmrBox.setValue(
        params_cfg['ctm_r'] if params_cfg['ctm_r'] is not None else params_widget.defaults['ctmradius'])
    params_widget.sampenCBox.setChecked(bool(params_cfg['sample_entropy']))
    params_widget.sampenrBox.setValue(
        params_cfg['sample_entropy_r'] if params_cfg['sample_entropy_r'] is not None else params_widget.defaults[
            'sampradius'])
    params_widget.sampenmBox.setValue(
        params_cfg['sample_entropy_m'] if params_cfg['sample_entropy_m'] is not None else params_widget.defaults[
            'sampm'])
    params_widget.msampenCBox.setChecked(bool(params_cfg['multiscale_sample_entropy']))
    params_widget.msampenrBox.setValue(
        params_cfg['multiscale_sample_entropy_r'] if params_cfg['multiscale_sample_entropy_r'] is not None else
        params_widget.defaults['multisampradius'])
    params_widget.msampenmBox.setValue(
        params_cfg['multiscale_sample_entropy_m'] if params_cfg['multiscale_sample_entropy_m'] is not None else
        params_widget.defaults['multisampm'])
    params_widget.msampenscaleBox.setValue(
        params_cfg['multiscale_sample_entropy_scale'] if params_cfg['multiscale_sample_entropy_scale'] is not None else
        params_widget.defaults['multisampmaxscale'])
    params_widget.lzcCBox.setChecked(bool(params_cfg['lzc']))
    params_widget.mlzcCBox.setChecked(bool(params_cfg['multiscale_lzc']))
    if params_cfg['multiscale_lzc_scales'] is not None:
        params_widget.mlzcEdit.setText(str(params_cfg['multiscale_lzc_scales']))
    params_widget.iacCBox.setChecked(bool(params_cfg['iac']))
    params_widget.iacortButton.setChecked(bool(params_cfg['ort_iac']))
    params_widget.aecCBox.setChecked(bool(params_cfg['aec']))
    params_widget.aecortButton.setChecked(bool(params_cfg['ort_aec']))
    params_widget.pliCBox.setChecked(bool(params_cfg['pli']))
    params_widget.plvCBox.setChecked(bool(params_cfg['plv']))
    params_widget.wpliCBox.setChecked(bool(params_cfg['wpli']))
    # Store
    files_widget.main_window.controller.parameters_config = params_cfg

if __name__ == '__main__':
    with open(rf"C:\Users\1993_\Desktop\config_Good.json") as json_data:
        state = json.load(json_data)
        json_data.close()
    run_pipeline(state)
