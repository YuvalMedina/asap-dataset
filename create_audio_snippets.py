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

def read_annotations(annotations_path):
    with open(annotations_path, 'r') as annotations_file:
        annotations = []
        while True:
            try:
                line = next(annotations_file).split('\t')
            except StopIteration:
                break
            annotations.append([line[1], line[2]])
        return annotations
    
def make_snippets(audio_length, sr, snippets_length):
    snippets_samples_length = sr * snippets_length
    quotient, remainder = divmod(audio_length, snippets_samples_length)
    if quotient == 0:
        return [[0, audio_length]]
    if remainder > snippets_samples_length * 0.7:
        return [[i*snippets_samples_length, i*snippets_samples_length+snippets_samples_length] for i in len(quotient)] + [quotient*snippets_samples_length, quotient*snippets_samples_length+remainder]
    return [[i*audio_length/(quotient+1), (i+1)*audio_length/(quotient+1)] for i in range(quotient+1)]

def make_snippets_annotations(annotations, snippets):
    snippets_annotations = []
    for snippet in snippets:
        start = snippet[0]
        end = snippet[1]
        snippets_annotations.append([annotation for annotation in annotations if annotation[0] >= start and annotation[0] < end])
    return snippets_annotations

def make_snippet_xml(xml_score, snippets_annotations, snippets_annotations_index, snippet_start, snippet_end, sr):
    snippet_start = snippet_start / sr
    snippet_end = snippet_end / sr

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
    for annotation in snippets_annotations[snippets_annotations_index][1:]:
        if annotation[1].startswith('db'):
            end_measure += 1
            end_measure_timestamp = annotation[1]
    xml_score = xml_score.measures(start_measure, end_measure)
    if abs(start_measure_timestamp - snippet_start) > 0.01:
        xml_score

def make_snippets(output_folder_path, in_audio_path, in_xml_path, in_annotations_path, snippets_length, padding=0.5):
    annotations = read_annotations(in_annotations_path)
    xml_score = converter.parse(in_xml_path)
    audio_data, sr = librosa.core.load(in_audio_path, sr=None, mono=False)
    snippets, snippets_annotations = make_snippets(len(audio_data), annotations, sr, snippets_length)
    for i in range(len(snippets)):
        snippet = snippets[i]
        file_name = '_'.join(in_audio_path[:-4].split('/') + i)
        out_audio_path = Path.joinpath(output_folder_path, file_name + '.wav')
        start = snippet[0]
        end = snippet[1]
        librosa.output.write_wav(out_audio_path, y=audio_data[start:end].astype(np.float32), sr=sr, mono=False)

        out_xml_path = Path.joinpath(output_folder_path, file_name + '.musicxml')
        snippet_xml = make_snippet_xml(xml_score, snippets_annotations, i, start, end, sr)
        snippet_xml.write('musicxml', out_xml_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create snippets of performed audio and corresponding MusicXML scores.',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    
    parser.add_argument('-l', '--snippets_length', help='The length of the snippets in seconds.',
                        default=12.8, type=float)
        
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
        break
        if counter%20 == 0:
            print("{}/520 completed".format(counter))