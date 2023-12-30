import datetime

import kfp
import kfp.dsl as dsl

from typing import Dict, List

from kfp import compiler
from kfp.dsl import Artifact, Input, Output

videos = [
    f"gs://video-frame-classification/JaneGoodall.mp4",
]

@dsl.component(
    base_image='python:3.11',
    packages_to_install=['opencv-python-headless']
)
def extract_images(video_filepath: str, import_filepath: str):
    import cv2
    import json
    import os

    DIRECTORY = video_filepath.replace(f"gs://video-frame-classification/", "").replace(".mp4", "")

    # Open video file and get the frame rate (FPS)
    cap = cv2.VideoCapture(video_filepath.replace("gs://", "/gcs/"))
    fps = cap.get(cv2.CAP_PROP_FPS)

    if not cap.isOpened():
        raise Exception("Could not open the video file")

    # Get one frame per second (~1/60 sampling)
    for i in range(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), int(fps)):
        # Set the frame position
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)

        # Read frame
        ret, frame = cap.read()

        if ret:
            # Write frame to GCS
            if not os.path.exists(f"/gcs/video-frame-classification/{DIRECTORY}"):
                os.makedirs(f"/gcs/video-frame-classification/{DIRECTORY}")
            cv2.imwrite(
                f"/gcs/video-frame-classification/{DIRECTORY}/{i}.png",
                frame
            )
            # Write image filepath to a import file
            with open(import_filepath.replace("gs://", "/gcs/"), "a") as f:
                f.write(
                    json.dumps({
                        "imageGcsUri": f"gs://video-frame-classification/{DIRECTORY}/{i}.png",
                    }) + "\n"
                )
        else:
            print("Could not read frame:", i)

    # Release video
    cap.release()


@dsl.pipeline(
    name="frame-extraction"
)
def frame_extraction():
    now = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    with dsl.ParallelFor(
        name="videos",
        items=videos,
        parallelism=1
    ) as video:
        extract_images_task = extract_images(
            video_filepath=video,
            import_filepath=f"gs://video-frame-classification/import-{now}.jsonl"
        )

compiler.Compiler().compile(frame_extraction, 'pipeline.json')