"""Given a snippet length (or the default of 12.8s) this script will create snippets of each of the audio performances
as well as corresponding snippets of the Musicl XML scores."""
import argparse
import pandas as pd
import os
import librosa
from shutil import copyfile
import numpy as np
from pathlib import Path   
import math
from music21 import *
import copy

def read_annotations(annotations_path):
    with open(annotations_path, 'r') as annotations_file:
        annotations = []
        while True:
            try:
                line = next(annotations_file).split('\t')
            except StopIteration:
                break
            annotations.append([float(line[0]), line[2]])
        return annotations
    
def make_snippet_times(audio_length, sr, snippets_length):
    snippets_samples_length = sr * snippets_length
    quotient, remainder = divmod(audio_length, snippets_samples_length)
    if quotient == 0:
        return [[0, int(audio_length)]]
    if remainder > snippets_samples_length * 0.7:
        return [[int(i*snippets_samples_length), int(i*snippets_samples_length+snippets_samples_length)] for i in range(int(quotient))] + [[int(quotient*snippets_samples_length), int(quotient*snippets_samples_length+remainder)]]
    return [[int(i*audio_length/(quotient+1)), int((i+1)*audio_length/(quotient+1))] for i in range(int(quotient)+1)]

def make_snippets_annotations(annotations, sr, snippet_times):
    snippets_annotations = []
    for snippet_duration in snippet_times:
        start = float(snippet_duration[0]) / sr
        end = float(snippet_duration[1]) / sr
        snippets_annotations.append([annotation for annotation in annotations if annotation[0] >= start and annotation[0] < end])
    return snippets_annotations

def delete_first_beats(xml_score, start_measure, start_beat):
    xml_score = copy.deepcopy(xml_score)
    start_offset = start_beat - 1
    for measure in xml_score.recurse(classFilter=('Measure')):
        if measure.number == start_measure:
            removed = set()
            for note_or_rest in measure.recurse(classFilter=('Note', 'Rest')):
                if note_or_rest.offset < start_offset:
                    removed.add(note_or_rest.activeSite)
                    note_or_rest.activeSite.remove(note_or_rest)
            for stream in removed: stream.insert(0, note.Rest())
    return xml_score

def delete_last_beats(xml_score, end_measure, end_beat):
    xml_score = copy.deepcopy(xml_score)
    end_offset = end_beat - 1
    for measure in xml_score.recurse(classFilter=('Measure')):
        if measure.number == end_measure:
            removed = set()
            for note_or_rest in measure.recurse(classFilter=('Note', 'Rest')):
                if note_or_rest.offset > end_offset:
                    removed.add(note_or_rest.activeSite)
                    note_or_rest.activeSite.remove(note_or_rest)
            for stream in removed: stream.insert(end_beat, note.Rest())
    return xml_score

def make_snippet_xml(xml_score, snippets_annotations, snippets_annotations_index, snippet_start, snippet_end, sr):
    snippet_start = snippet_start / sr
    snippet_end = snippet_end / sr
    xml_score = copy.deepcopy(xml_score)

    start_measure = 1
    start_measure_timestamp = 0
    for i in range(snippets_annotations_index):
        for annotation in snippets_annotations[i]:
            if annotation[1].startswith('db'):
                start_measure += 1
                start_measure_timestamp = annotation[0]
    start_beat = 1
    if snippets_annotations[snippets_annotations_index][0][1].startswith('db'):
        start_measure += 1
        start_measure_timestamp = snippets_annotations[snippets_annotations_index][0][0]
    elif snippets_annotations_index > 0:
        start_beat = 2
        for annotation in reversed(snippets_annotations[snippets_annotations_index-1]):
            if annotation[1].startswith('db'): break
            start_beat += 1
    
    end_measure = start_measure
    end_measure_timestamp = start_measure_timestamp
    end_beat = None
    for annotation in snippets_annotations[snippets_annotations_index][1:]:
        if annotation[1].startswith('db'):
            end_measure += 1
            end_measure_timestamp = annotation[1]
            end_beat = 1
        else:
            if end_beat: end_beat += 1
            else: end_beat = 1

    xml_score = xml_score.measures(start_measure, end_measure)
    if start_beat > 1:
        xml_score = delete_first_beats(xml_score, start_measure, start_beat)
    if end_beat:
        xml_score = delete_last_beats(xml_score, end_measure, end_beat)
    return xml_score

def make_snippets(output_folder_path, in_audio_path, in_xml_path, in_annotations_path, snippets_length, padding=0.5):
    annotations = read_annotations(in_annotations_path)
    xml_score = converter.parse(in_xml_path)
    audio_data, sr = librosa.core.load(in_audio_path, sr=None, mono=False)
    snippet_times = make_snippet_times(audio_data.shape[1], sr, snippets_length)
    snippets_annotations = make_snippets_annotations(annotations, sr, snippet_times)
    for i in range(len(snippet_times)):
        snippet_start_end = snippet_times[i]
        file_name = '_'.join(in_audio_path[:-4].split('/') + [str(i)])
        out_audio_path = Path(output_folder_path, file_name + '.wav')
        start = snippet_start_end[0]
        end = snippet_start_end[1]
        librosa.output.write_wav(out_audio_path, y=audio_data[:, start:end].astype(np.float32), sr=sr, norm=False)

        out_xml_path = Path(output_folder_path, file_name + '.musicxml')
        snippet_xml = make_snippet_xml(xml_score, snippets_annotations, i, start, end, sr)
        snippet_xml.write('musicxml', out_xml_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create snippets of performed audio and corresponding MusicXML scores.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument('-l', '--snippets_length', help='The length of the snippets in seconds.',
                        default=25.6, type=float)
        
    parser.add_argument('--metadata', help='The correspondence.csv metadata file.',
                        default='metadata.csv', type=pd.read_csv)
    
    parser.add_argument('-o', '--output_folder', help='The output folder for the snippets.',
                        default='snippets/', type=str)
    
    args = parser.parse_args()
    
    print("Creating snippets of audio performances and Music XML scores")
    counter = 0
    for idx, row in args.metadata.iterrows():
        # Check that there is an audio performance for the corresponding piece
        if not row.isna()["audio_performance"]:
            try:
                make_snippets(args.output_folder,
                              str(Path(row["audio_performance"])),
                              str(Path(row["xml_score"])),
                              str(Path(row["performance_annotations"])),
                              args.snippets_length)
            except Exception as e:
                print("Failed for", idx,row["audio_performance"])
                print(e)
            counter+=1
        if counter%20 == 0:
            print("{}/520 completed".format(counter))