import flet as ft
import polars as pl
from src.pipeline import BibliometricPipeline
from src.core.collection import UnifiedCollector
import os
import threading
import logging
import asyncio

# Global state for managing concurrent access in web mode
pipeline_lock = threading.Lock()
is_busy = False

async def main(page: ft.Page):
    page.title = "Bibliometric Research Pipeline"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 30
    
    # UI Components
    status_text = ft.Text("Ready to start", size=16, color=ft.Colors.GREY_700)
    progress_bar = ft.ProgressBar(width=400, color="blue", visible=False)
    selected_file_text = ft.Text("No data source selected", italic=True)
    
    # Collection Components
    search_query = ft.TextField(label="Search Query (e.g., 'brain-computer interface')", expand=True)
    fetch_limit = ft.Dropdown(
        label="Limit/Source",
        options=[
            ft.dropdown.Option("50"),
            ft.dropdown.Option("100"),
            ft.dropdown.Option("200"),
            ft.dropdown.Option("500"),
        ],
        value="100",
        width=120
    )
    
    start_year_input = ft.TextField(label="Start Year", width=100, hint_text="2020")
    end_year_input = ft.TextField(label="End Year", width=100, hint_text="2024")

    source_selection = ft.Dropdown(
        label="Sources",
        options=[
            ft.dropdown.Option("all", "All Sources"),
            ft.dropdown.Option("openalex", "OpenAlex Only"),
            ft.dropdown.Option("semantic_scholar", "Semantic Scholar Only"),
            ft.dropdown.Option("crossref", "Crossref Only"),
        ],
        value="all",
        width=200
    )

    # State
    pipeline = BibliometricPipeline(output_dir="pipeline_results")
    collector = UnifiedCollector()
    selected_path = None

    async def on_file_result(e: ft.FilePickerResultEvent):
        nonlocal selected_path
        if e.files:
            selected_path = e.files[0].path
            selected_file_text.value = f"Selected File: {os.path.basename(selected_path)}"
            status_text.value = "File loaded. Ready to run pipeline."
            status_text.color = ft.Colors.BLACK
            run_btn.disabled = False
            await page.update_async()

    file_picker = ft.FilePicker(on_result=on_file_result)
    page.overlay.append(file_picker)

    def fetch_data_thread():
        nonlocal selected_path
        global is_busy
        try:
            is_busy = True
            status_text.value = f"Fetching papers for '{search_query.value}'..."
            status_text.color = ft.Colors.BLUE
            progress_bar.visible = True
            fetch_btn.disabled = True
            page.update()

            limit = int(fetch_limit.value)
            start_y = int(start_year_input.value) if start_year_input.value else None
            end_y = int(end_year_input.value) if end_year_input.value else None
            sources = None if source_selection.value == "all" else [source_selection.value]

            df = collector.fetch_all(search_query.value, limit_per_source=limit, sources=sources, start_year=start_y, end_year=end_y)
            
            if df.empty:
                status_text.value = "No papers found for this query."
                status_text.color = ft.Colors.RED
                return

            # Save to a temporary file in data directory
            os.makedirs("data", exist_ok=True)
            safe_query = search_query.value.replace(' ', '_').replace('/', '_')
            filename = f"data/collected_{safe_query}.csv"
            df.to_csv(filename, index=False)
            
            selected_path = filename
            selected_file_text.value = f"Fetched Data: {os.path.basename(selected_path)} ({len(df)} papers)"
            status_text.value = f"Successfully collected {len(df)} papers. Ready to run pipeline."
            status_text.color = ft.Colors.GREEN
            run_btn.disabled = False
        except Exception as ex:
            status_text.value = f"Error during collection: {str(ex)}"
            status_text.color = ft.Colors.RED
        finally:
            is_busy = False
            progress_bar.visible = False
            fetch_btn.disabled = False
            page.update()

    def handle_fetch_click(e):
        if not search_query.value:
            status_text.value = "Please enter a search query."
            status_text.color = ft.Colors.ORANGE
            page.update()
            return
        threading.Thread(target=fetch_data_thread, daemon=True).start()

    def run_pipeline_thread():
        global is_busy
        if not pipeline_lock.acquire(blocking=False):
            status_text.value = "System is busy. Another user is running a pipeline. Please wait."
            status_text.color = ft.Colors.ORANGE
            page.update()
            return

        try:
            is_busy = True
            status_text.value = "Running end-to-end pipeline (NLP, Networks, Viz)..."
            status_text.color = ft.Colors.BLUE
            progress_bar.visible = True
            run_btn.disabled = True
            page.update()

            # Execute the modular pipeline
            pipeline.run(selected_path)

            status_text.value = f"Success! Results saved to '{pipeline.output_dir}' folder."
            status_text.color = ft.Colors.GREEN
        except Exception as ex:
            status_text.value = f"Error during execution: {str(ex)}"
            status_text.color = ft.Colors.RED
        finally:
            is_busy = False
            progress_bar.visible = False
            run_btn.disabled = False
            pipeline_lock.release()
            page.update()

    def handle_run_click(e):
        if is_busy:
            status_text.value = "System Busy: Another process is currently using the GPU."
            status_text.color = ft.Colors.ORANGE
            page.update()
            return

        if selected_path:
            # Run in a thread to keep UI responsive
            threading.Thread(target=run_pipeline_thread, daemon=True).start()

    fetch_btn = ft.FilledButton(
        "Fetch Data",
        icon=ft.Icons.CLOUD_DOWNLOAD,
        on_click=handle_fetch_click,
        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.GREEN_700)
    )

    run_btn = ft.FilledButton(
        "Run Full Pipeline", 
        icon=ft.Icons.PLAY_ARROW, 
        on_click=handle_run_click,
        disabled=True,
        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.BLUE)
    )

    # Layout Construction
    await page.add_async(
        ft.Column([
            ft.Text("Bibliometric Autopilot", size=40, weight=ft.FontWeight.BOLD),
            ft.Text("Modular Research Pipeline (BERTopic + cuGraph)", size=18, color=ft.Colors.GREY_600),
            ft.Divider(height=20),
            
            ft.Row([
                # Left Column: Data Input
                ft.Column([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Option A: Autonomous Collection", size=20, weight=ft.FontWeight.W_600),
                            ft.Row([search_query, fetch_limit]),
                            ft.Row([start_year_input, end_year_input, source_selection]),
                            fetch_btn,
                        ], spacing=10),
                        padding=20, border=ft.Border(ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300)), border_radius=10, width=600
                    ),
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Option B: Manual Upload", size=20, weight=ft.FontWeight.W_600),
                            ft.Row([
                                ft.FilledButton("Pick CSV/Parquet", icon=ft.Icons.FILE_OPEN, on_click=lambda _: file_picker.pick_files()),
                            ]),
                        ], spacing=10),
                        padding=20, border=ft.Border(ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300)), border_radius=10, width=600
                    ),
                ], spacing=20),
                
                # Right Column: Execution
                ft.Column([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Step 2: Execution", size=20, weight=ft.FontWeight.W_600),
                            selected_file_text,
                            run_btn,
                            progress_bar,
                            status_text,
                        ], spacing=10),
                        padding=20, border=ft.Border(ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300), ft.BorderSide(1, ft.Colors.GREY_300)), border_radius=10, width=400
                    ),
                ]),
            ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.START),
            
            ft.Divider(height=40),
            ft.Text("Project Architecture: src/core (Collection, Ingestion, NLP, Network, Viz)", size=12, color=ft.Colors.GREY_400)
        ], spacing=20)
    )

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.WEB_BROWSER, port=8550)
