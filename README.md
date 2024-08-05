# AutoClipper

**AutoClipper** is an innovative bot that harnesses the power of Large Language Models (LLMs) to autonomously clip streamers and create video compilations. This project exemplifies advanced AI integration, video processing, and automation capabilities.

## Features

- **Autonomous Clipping**: Uses LLMs to identify the best clips from a stream or given period.
- **Video Compilation**: Automatically compiles the clips into cohesive video highlights.
- **Customizable Rules**: Easily update prompts and rules for clip selection and ordering.

## Getting Started

### Prerequisites

- **Python**: Ensure you have Python 3.x installed.
- **Virtual Environment**: Optional but recommended for dependency management.

### Installation

1. **Clone the Repository**:
    ```bash
    git clone https://github.com/Stermere/AutoClipper
    cd AutoClipper
    ```

2. **Set Up the Virtual Environment** (optional but recommended):
    ```bash
    python -m venv venv
    ./venv/Scripts/activate
    ```

3. **Install the Dependencies**:
    ```bash
    python -m pip install -r requirments.txt
    ```
    
### Running AutoClipper

- Execute the main script:
    ```bash
    python Main.py <task>
    ```

Where <task> can be one of the following:

1. `-v`: Render a video.

    ```bash
    python Main.py -v streamer_name target_stream
    ```
    - `streamer_name`: The name of the streamer.
    - `target_stream` (optional): The number of VODs back from the latest to consider.

2. `-mv`: Schedule multiple short videos.

    ```bash
    python Main.py -mv num_videos days_back streamer_names
    ```
    - `num_videos`: Number of videos to create.
    - `days_back`: Number of days back to consider for clips.
    - `streamer_names`: List of streamer names.

3. `-r`: Register with the YouTube API.

    ```bash
    python Main.py -r
    ```

4. `-clean`: Delete all clips in the clip directory.

    ```bash
    python Main.py -clean
    ```

5. `--h`: Display the help menu.

    ```bash
    python Main.py --h
    ```
