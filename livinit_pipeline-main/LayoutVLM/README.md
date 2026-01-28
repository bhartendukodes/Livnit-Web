# LayoutVLM

<div align="left">
    <a href="https://ai.stanford.edu/~sunfanyun/layoutvlm"><img src="https://img.shields.io/badge/🌐 Website-Visit-orange"></a>
    <a href=""><img src="https://img.shields.io/badge/arXiv-PDF-blue"></a>
</div>

<br>

## Architecture Overview

```mermaid
flowchart TB
    subgraph Input
        JSON[Scene JSON Config]
        Assets[Objaverse Assets]
    end

    subgraph LayoutVLM["LayoutVLM System"]
        Main[main.py]
        Solver[LayoutVLM Solver]
        Sandbox[SandBox Environment]
        GradSolver[Gradient Solver]
        
        subgraph LLMs["LLM Services"]
            GPT4o[GPT-4o]
            GPT4oMini[GPT-4o-mini]
        end
    end

    subgraph Output
        Layout[layout.json]
        GIF[Optimization GIF]
    end

    JSON --> Main
    Assets --> Main
    Main --> Solver
    Solver --> GPT4o
    Solver --> GPT4oMini
    Solver --> Sandbox
    Sandbox --> GradSolver
    GradSolver --> Layout
    Solver --> GIF
```

## Solve Flow

```mermaid
flowchart TD
    Start([Start]) --> LoadConfig[Load Scene Config]
    LoadConfig --> PrepareAssets[Prepare Task Assets]
    PrepareAssets --> InitSandbox[Initialize SandBox Environment]
    InitSandbox --> GetGroups{Has Provided Groups?}
    
    GetGroups -->|Yes| UseProvided[Use Provided Groups]
    GetGroups -->|No| LLMGrouping[LLM Asset Grouping]
    
    UseProvided --> GroupLoop
    LLMGrouping --> GroupLoop
    
    subgraph GroupLoop["For Each Group"]
        RenderScene[Render Scene Images]
        RenderScene --> BuildPrompt[Build Constraint Prompt]
        BuildPrompt --> LLMConstraint[LLM Generate Constraints]
        LLMConstraint --> ExecuteConstraint[Execute in Sandbox]
        ExecuteConstraint --> Optimize[Gradient Optimization]
        Optimize --> UpdatePlaced[Update Placed Assets]
    end
    
    GroupLoop --> Unplaced{Unplaced Assets?}
    Unplaced -->|Yes| PlaceRemaining[Place Remaining Assets]
    PlaceRemaining --> Unplaced
    Unplaced -->|No| Export[Export Layout]
    Export --> SaveGIF[Save Optimization GIF]
    SaveGIF --> End([End])
```

## Single Group Solve Flow

```mermaid
sequenceDiagram
    participant Main as LayoutVLM
    participant Blender as Blender Renderer
    participant LLM as GPT-4o
    participant Sandbox as SandBox
    participant Solver as GradSolver

    Main->>Blender: Render current scene
    Blender-->>Main: Top-down & side images
    
    Main->>Main: Build prompt with task program
    Main->>LLM: Send prompt + images
    LLM-->>Main: Constraint program (Python)
    
    Main->>Sandbox: Execute constraint program
    Sandbox->>Solver: Run gradient optimization
    
    loop Until Converged
        Solver->>Solver: Compute constraint losses
        Solver->>Solver: Backpropagate gradients
        Solver->>Solver: Update positions/rotations
    end
    
    Solver-->>Sandbox: Optimized placements
    Sandbox-->>Main: Updated placed assets
```

## Installation

1. Clone this repository
2. Install dependencies (python 3.10):
```bash
pip install -r requirements.txt
```
3. Install Rotated IOU Loss (https://github.com/lilanxiao/Rotated\_IoU)
```
cd third_party/Rotated_IoU/cuda_op
python setup.py install
````

## Data preprocessing
1. Download the dataset https://drive.google.com/file/d/1WGbj8gWn-f-BRwqPKfoY06budBzgM0pu/view?usp=sharing
2. Unzip it.

Refer to https://github.com/allenai/Holodeck and https://github.com/allenai/objathor for how we preprocess Objaverse assets.

## Usage

1. Prepare a scene configuration JSON file of Objaverse assets with the following structure:
```json
{
    "task_description": ...,
    "layout_criteria": ...,
    "boundary": {
        "floor_vertices": [[x1, y1, z1], [x2, y2, z2], ...],
        "wall_height": height
    },
    "assets": {
        "asset_id": {
            "path": "path/to/asset.glb",
            "assetMetadata": {
                "boundingBox": {
                    "x": width,
                    "y": depth,
                    "z": height
                }
            }
        }
    }
}
```

2. Run LayoutVLM:
```bash
python main.py --scene_json_file path/to/scene.json --openai_api_key your_api_key
```

## Output
The script will generate a layout.json file in the specified save directory containing the optimized positions and orientations of all assets in the scene.

## BibTeX
```bibtex
@inproceedings{sun2025layoutvlm,
  title={Layoutvlm: Differentiable optimization of 3d layout via vision-language models},
  author={Sun, Fan-Yun and Liu, Weiyu and Gu, Siyi and Lim, Dylan and Bhat, Goutam and Tombari, Federico and Li, Manling and Haber, Nick and Wu, Jiajun},
  booktitle={Proceedings of the Computer Vision and Pattern Recognition Conference},
  pages={29469--29478},
  year={2025}
}
```
