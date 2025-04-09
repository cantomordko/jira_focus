import json
import os
import re
import sys
import time
import traceback
from collections import Counter
from tkinter import messagebox
import customtkinter as ctk
import requests

TERMINAL_GREEN = "#32CD32"
TERMINAL_GREEN_BRIGHT = "#7FFF00"
BACKGROUND_COLOR = "#111111"
WIDGET_BACKGROUND = "#222222"
BORDER_COLOR = TERMINAL_GREEN
HOVER_COLOR_BTN = "#333333"
TEXT_COLOR_NORMAL = TERMINAL_GREEN
TEXT_COLOR_DIM = "#777777"
ERROR_RED = "#CC0000"
STATUS_BLUE = "#0088CC"
STATUS_ORANGE = "#FFA500"
STATUS_GREEN = "#00AA00"
LABEL_NEW_FG = "#90EE90"

FONT_FAMILY_MONO = "Courier New"
FONT_MONO_NORMAL = (FONT_FAMILY_MONO, 13)
FONT_MONO_BOLD = (FONT_FAMILY_MONO, 13, "bold")
FONT_MONO_LARGE = (FONT_FAMILY_MONO, 17)
FONT_MONO_XLARGE = (FONT_FAMILY_MONO, 22, "bold")
FONT_MONO_SMALL = (FONT_FAMILY_MONO, 11)


class LabelEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent_gui):
        super().__init__(parent_gui.root)
        self.parent_gui = parent_gui
        self.transient(parent_gui.root)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.attributes('-alpha', 0.95)

        self.configure(fg_color=BACKGROUND_COLOR)

        self.initial_labels_for_existing_task = set()
        self.current_selection_vars = {}
        self.project_available_labels = []

        if not self.parent_gui.selected_project_key and not self.parent_gui.current_jira_issue_key:
            if self.parent_gui.root and self.parent_gui.root.winfo_exists():
                messagebox.showerror("Error", "Select a project or load a task first.", parent=self)
            else:
                print("Error: Attempted to open label editor without project or task context.")
            self.destroy()
            return

        if self.parent_gui.current_jira_issue_key:
            self.title(f"LABELS::{self.parent_gui.current_jira_issue_key}")
        else:
            self.title(f"LABELS::NEW_TASK::{self.parent_gui.selected_project_key}")
        self.geometry("400x450")

        try:
            if self.parent_gui.root and self.parent_gui.root.winfo_exists():
                main_x, main_y = self.parent_gui.root.winfo_x(), self.parent_gui.root.winfo_y()
                main_w, main_h = self.parent_gui.root.winfo_width(), self.parent_gui.root.winfo_height()
                win_w, win_h = 400, 450
                self.geometry(
                    f"{win_w}x{win_h}+{main_x + (main_w // 2) - (win_w // 2)}+{main_y + (main_h // 2) - (win_h // 2)}")
        except Exception as e:
            print(f"Could not center label editor window: {e}")

        if self.parent_gui.current_jira_issue_key:
            info_text = f"EDIT LABELS FOR TASK: {self.parent_gui.current_jira_issue_key}"
        else:
            info_text = f"SELECT LABELS FOR NEW TASK IN PROJECT: {self.parent_gui.selected_project_key}"
        self.info_label = ctk.CTkLabel(self, text=info_text, font=FONT_MONO_NORMAL, wraplength=380,
                                       text_color=TEXT_COLOR_NORMAL)
        self.info_label.pack(pady=(10, 5), padx=10)

        self.labels_scroll_frame = ctk.CTkScrollableFrame(
            self, height=250,
            fg_color=WIDGET_BACKGROUND,
            label_text_color=TEXT_COLOR_NORMAL, label_font=FONT_MONO_SMALL,
            scrollbar_button_color=TERMINAL_GREEN, scrollbar_button_hover_color=TERMINAL_GREEN_BRIGHT,
            corner_radius=0, border_width=1, border_color=BORDER_COLOR
        )
        self.labels_scroll_frame.pack(fill='x', padx=10, pady=(0, 5))
        self.labels_scroll_frame.grid_columnconfigure(0, weight=1)

        self.add_label_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.add_label_frame.pack(fill='x', padx=10, pady=(5, 10))

        self.new_label_entry = ctk.CTkEntry(
            self.add_label_frame,
            placeholder_text="add new label >", font=FONT_MONO_NORMAL, corner_radius=0,
            fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            placeholder_text_color=TEXT_COLOR_DIM, border_width=1, border_color=BORDER_COLOR
        )
        self.new_label_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.new_label_entry.bind("<Return>", self._add_new_label_from_entry)

        self.add_label_button = ctk.CTkButton(
            self.add_label_frame, text="ADD", font=FONT_MONO_BOLD,
            width=60, command=self._add_new_label_from_entry,
            corner_radius=0, fg_color=TERMINAL_GREEN, text_color=BACKGROUND_COLOR,
            hover_color=TERMINAL_GREEN_BRIGHT
        )
        self.add_label_button.pack(side='left')

        self.action_button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_button_frame.pack(fill='x', padx=10, pady=(5, 10))
        self.action_button_frame.grid_columnconfigure((0, 1), weight=1)

        if self.parent_gui.current_jira_issue_key:
            self.update_button = ctk.CTkButton(
                self.action_button_frame, text="UPDATE [JIRA]",
                font=FONT_MONO_BOLD, command=self._update_jira_labels,
                fg_color=STATUS_GREEN, text_color=BACKGROUND_COLOR, hover_color=TERMINAL_GREEN_BRIGHT,
                corner_radius=0
            )
            self.update_button.grid(row=0, column=0, padx=(0, 5), sticky='ew')
        else:
            self.save_button = ctk.CTkButton(
                self.action_button_frame, text="SAVE [NEW TASK]",
                font=FONT_MONO_BOLD, command=self._save_labels_for_new_task_and_close,
                fg_color=STATUS_GREEN, text_color=BACKGROUND_COLOR, hover_color=TERMINAL_GREEN_BRIGHT,
                corner_radius=0
            )
            self.save_button.grid(row=0, column=0, padx=(0, 5), sticky='ew')

        self.cancel_button = ctk.CTkButton(
            self.action_button_frame, text="CANCEL", font=FONT_MONO_BOLD,
            command=self.destroy,
            fg_color=TEXT_COLOR_DIM, text_color=BACKGROUND_COLOR, hover_color=HOVER_COLOR_BTN,
            corner_radius=0
        )
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), sticky='ew')

        self._load_data_and_populate()

    def _load_data_and_populate(self):
        loading_label = ctk.CTkLabel(self.labels_scroll_frame, text="loading labels...", font=FONT_MONO_SMALL,
                                     text_color=TEXT_COLOR_NORMAL)
        loading_label.pack(pady=10)
        try:
            self.update_idletasks()
        except Exception:
            pass

        try:
            project_labels = self._fetch_project_labels()
            self.project_available_labels = project_labels

            task_labels = set()
            if self.parent_gui.current_jira_issue_key:
                task_labels = self._fetch_current_task_labels()
                self.initial_labels_for_existing_task = task_labels.copy()

            combined_labels = set(project_labels)
            if self.parent_gui.current_jira_issue_key:
                combined_labels.update(task_labels)
            else:
                combined_labels.update(self.parent_gui.selected_labels)
            sorted_labels_to_display = sorted(list(combined_labels))

            if loading_label and loading_label.winfo_exists(): loading_label.destroy()

            for widget in self.labels_scroll_frame.winfo_children():
                if isinstance(widget, (ctk.CTkLabel, ctk.CTkCheckBox)):
                    if widget.winfo_exists(): widget.destroy()
            self.current_selection_vars = {}

            if not sorted_labels_to_display:
                ctk.CTkLabel(self.labels_scroll_frame, text="// no labels found", font=FONT_MONO_SMALL,
                             text_color=TEXT_COLOR_DIM).pack(pady=5)
            else:
                for label_name in sorted_labels_to_display:
                    var = ctk.StringVar(value="off")
                    is_selected = False

                    if self.parent_gui.current_jira_issue_key:
                        if label_name in task_labels:
                            var.set("on")
                            is_selected = True
                    else:
                        if label_name in self.parent_gui.selected_labels:
                            var.set("on")
                            is_selected = True

                    cb = ctk.CTkCheckBox(
                        self.labels_scroll_frame, text=label_name, variable=var,
                        onvalue="on", offvalue="off",
                        font=FONT_MONO_NORMAL,
                        text_color=TEXT_COLOR_NORMAL if is_selected else TEXT_COLOR_DIM,
                        fg_color=TERMINAL_GREEN if is_selected else WIDGET_BACKGROUND,
                        hover_color=TERMINAL_GREEN_BRIGHT,
                        checkmark_color=BACKGROUND_COLOR,
                        corner_radius=0, border_width=1, border_color=BORDER_COLOR
                    )
                    cb.configure(command=lambda v=var, c=cb: c.configure(
                        text_color=TEXT_COLOR_NORMAL if v.get() == "on" else TEXT_COLOR_DIM,
                        fg_color=TERMINAL_GREEN if v.get() == "on" else WIDGET_BACKGROUND
                    )
                                 )
                    cb.pack(anchor='w', padx=5, pady=1, fill='x')
                    self.current_selection_vars[label_name] = var

        except Exception as e:
            print(f"[Editor] ERROR loading/populating labels: {e}")
            traceback.print_exc()
            if loading_label and loading_label.winfo_exists(): loading_label.destroy()
            try:
                for widget in self.labels_scroll_frame.winfo_children():
                    if isinstance(widget, (ctk.CTkLabel, ctk.CTkCheckBox)):
                        if widget.winfo_exists(): widget.destroy()
                ctk.CTkLabel(self.labels_scroll_frame, text=f"!! LOAD ERROR !!\n{e}", font=FONT_MONO_SMALL,
                             text_color=ERROR_RED, wraplength=350).pack(pady=10)
            except Exception as e_disp:
                print(f"Cannot display error in label editor window: {e_disp}")

    def _fetch_project_labels(self):
        if not self.parent_gui.selected_project_key: return []
        print(f"[Editor] Fetching labels for project {self.parent_gui.selected_project_key}...")
        jql = f'project = "{self.parent_gui.selected_project_key}" ORDER BY updated DESC'
        fields = "labels"
        max_results_per_page = 200
        start_at = 0
        all_labels_list = []
        total_fetched = 0

        while True:
            endpoint = f"search?jql={requests.utils.quote(jql)}&fields={fields}&maxResults={max_results_per_page}&startAt={start_at}"
            result = self.parent_gui._make_jira_request("GET", endpoint)

            if result and result['success'] and 'data' in result and 'issues' in result['data']:
                issues = result['data']['issues']
                if not issues: break

                batch_labels = [label for issue in issues if issue.get('fields', {}).get('labels')
                                for label in issue.get('fields', {}).get('labels', [])]
                all_labels_list.extend(batch_labels)

                total_fetched += len(issues)
                start_at += max_results_per_page

                if total_fetched >= result['data'].get('total', 0) or len(issues) < max_results_per_page:
                    break
            else:
                print(
                    f"[Editor] Failed fetching labels chunk for project {self.parent_gui.selected_project_key} at startAt={start_at}. Reason: {result.get('error', 'no data?')}")
                break

        project_labels = []
        if all_labels_list:
            label_counts = Counter(all_labels_list)
            project_labels = sorted(label_counts.keys(), key=lambda x: (-label_counts[x], x))
            print(f"[Editor] Found {len(project_labels)} unique project labels from {total_fetched} issues checked.")
        else:
            print(f"[Editor] No labels found across checked issues for project {self.parent_gui.selected_project_key}.")

        return project_labels

    def _fetch_current_task_labels(self):
        if not self.parent_gui.current_jira_issue_key:
            return set()

        print(f"[Editor] Fetching labels for task {self.parent_gui.current_jira_issue_key}...")
        endpoint = f"issue/{self.parent_gui.current_jira_issue_key}?fields=labels"
        result = self.parent_gui._make_jira_request("GET", endpoint)

        task_labels = set()
        if result and result['success'] and 'data' in result:
            task_labels = set(result['data'].get('fields', {}).get('labels', []))
            print(f"[Editor] Found labels for task {self.parent_gui.current_jira_issue_key}: {task_labels}")
        else:
            print(f"[Editor] Failed to fetch labels for task {self.parent_gui.current_jira_issue_key}.")
            error_msg = f"Cannot fetch labels for {self.parent_gui.current_jira_issue_key}."
            if result and not result['success']: error_msg += f"\nAPI Error: {result.get('error', 'None')[:100]}..."
            if self.winfo_exists():
                messagebox.showerror("Label Fetch Error", error_msg, parent=self)
        return task_labels

    def _add_new_label_from_entry(self, event=None):
        new_label = self.new_label_entry.get().strip()
        if not new_label: return

        if re.search(r"\s", new_label):
            messagebox.showwarning("Invalid Label", f"Label '{new_label}' contains spaces.", parent=self)
            return

        if new_label in self.current_selection_vars:
            print(f"[Editor] Label '{new_label}' already exists. Selecting...")
            if self.current_selection_vars[new_label]:
                try:
                    self.current_selection_vars[new_label].set("on")
                    for child in self.labels_scroll_frame.winfo_children():
                        if isinstance(child, ctk.CTkCheckBox) and child.cget("text") == new_label:
                            child.select()
                            child.configure(text_color=TEXT_COLOR_NORMAL, fg_color=TERMINAL_GREEN)
                            break
                except Exception as e_set:
                    print(f"Cannot set variable/update checkbox for {new_label}: {e_set}")
            if self.new_label_entry.winfo_exists(): self.new_label_entry.delete(0, "end")
            return

        print(f"[Editor] Adding new UI label: {new_label}")
        var = ctk.StringVar(value="on")
        cb = ctk.CTkCheckBox(
            self.labels_scroll_frame, text=new_label, variable=var,
            onvalue="on", offvalue="off",
            font=FONT_MONO_NORMAL,
            text_color=LABEL_NEW_FG,
            fg_color=TERMINAL_GREEN,
            hover_color=TERMINAL_GREEN_BRIGHT,
            checkmark_color=BACKGROUND_COLOR,
            corner_radius=0, border_width=1,
            border_color=LABEL_NEW_FG,
        )
        cb.configure(command=lambda v=var, c=cb: c.configure(
            text_color=TEXT_COLOR_NORMAL if v.get() == "on" else TEXT_COLOR_DIM,
            fg_color=TERMINAL_GREEN if v.get() == "on" else WIDGET_BACKGROUND,
            border_color=BORDER_COLOR
        )
                     )

        try:
            cb.pack(anchor='w', padx=5, pady=1, fill='x')
            self.current_selection_vars[new_label] = var
            if self.new_label_entry.winfo_exists(): self.new_label_entry.delete(0, "end")
        except Exception as e_pack:
            print(f"Error adding new checkbox UI for '{new_label}': {e_pack}")
            traceback.print_exc()
            if cb and cb.winfo_exists(): cb.destroy()

    def _get_selected_labels_from_ui(self):
        selected = set()
        for label_name, var in self.current_selection_vars.items():
            if var:
                try:
                    if var.get() == "on":
                        selected.add(label_name)
                except Exception as e_get:
                    print(f"Error reading var for label '{label_name}': {e_get}")
        return selected

    def _update_jira_labels(self):
        if not self.parent_gui.current_jira_issue_key:
            print("[Editor] Error: Attempting label update without selected task.")
            if self.winfo_exists(): self.destroy()
            return

        current_selection = self._get_selected_labels_from_ui()
        print(f"[Editor] Updating labels for {self.parent_gui.current_jira_issue_key} to: {current_selection}")

        if current_selection == self.initial_labels_for_existing_task:
            print("[Editor] No changes detected in labels. Update request not sent.")
            if self.winfo_exists():
                messagebox.showinfo("Info", "No changes detected in labels.", parent=self)
                self.destroy()
            return

        valid_labels_list = sorted([lbl for lbl in current_selection if lbl and not re.search(r"\s", lbl)])

        update_data = {"fields": {"labels": valid_labels_list}}
        print(f"[Editor] Sending label update data: {json.dumps(update_data)}")
        endpoint = f"issue/{self.parent_gui.current_jira_issue_key}"
        result = self.parent_gui._make_jira_request("PUT", endpoint, data=json.dumps(update_data))

        if result and result['success'] and result.get('status_code') in [200, 204]:
            print(f"[Editor] Successfully updated labels for {self.parent_gui.current_jira_issue_key}.")
            if self.winfo_exists():
                messagebox.showinfo("Success", f"Labels for task {self.parent_gui.current_jira_issue_key} updated.",
                                    parent=self)
                self.destroy()
        else:
            print(f"[Editor] Failed to update labels for {self.parent_gui.current_jira_issue_key}.")
            error_msg = f"Failed to update labels for {self.parent_gui.current_jira_issue_key}."
            if result and result.get('error'):
                error_msg += f"\nAPI Error: {result['error']}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', []);
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nDetails: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result and result.get('raw_response'):
                error_msg += f"\nServer Response ({result.get('status_code')}): {result['raw_response'][:200]}..."
            if self.winfo_exists(): messagebox.showerror("Label Update Error", error_msg, parent=self)

    def _save_labels_for_new_task_and_close(self):
        try:
            if not self.parent_gui.current_jira_issue_key:
                current_selection = self._get_selected_labels_from_ui()
                print(f"[Editor] Saving selected labels for new task: {current_selection}")
                self.parent_gui.selected_labels = current_selection
                if hasattr(self.parent_gui, 'edit_labels_button') and self.parent_gui.edit_labels_button.winfo_exists():
                    label_count = len(current_selection)
                    self.parent_gui.edit_labels_button.configure(text=f"LABELS [{label_count}]")
            else:
                print("[Editor] Closing editor for existing task (no save to parent state needed).")
        except Exception as e:
            print(f"[Editor] Error during save/close operation: {e}")
            traceback.print_exc()
        finally:
            if self.winfo_exists():
                self.destroy()

    def _on_closing(self):
        print("[Editor] Label editor window closed by user ('X' button).")
        self._save_labels_for_new_task_and_close()


class CreateTaskDialog(ctk.CTkToplevel):
    def __init__(self, parent_gui, parent_window, project_key, issue_types):
        super().__init__(parent_window)
        self.parent_gui = parent_gui
        self.parent_task_list_window = parent_window
        self.project_key = project_key
        self.issue_types = issue_types or []

        self.title(f"NEW TASK::{project_key}")
        self.geometry("400x250")
        self.configure(fg_color=BACKGROUND_COLOR)

        self.transient(parent_window)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.attributes('-alpha', 0.97)

        try:
            parent_x, parent_y = parent_window.winfo_x(), parent_window.winfo_y()
            parent_w, parent_h = parent_window.winfo_width(), parent_window.winfo_height()
            win_w, win_h = 400, 250
            self.geometry(
                f"{win_w}x{win_h}+{parent_x + (parent_w // 2) - (win_w // 2)}+{parent_y + (parent_h // 2) - (win_h // 2)}")
        except Exception as e:
            print(f"Could not center create task dialog: {e}")

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(padx=15, pady=15, fill="both", expand=True)

        self.info_label = ctk.CTkLabel(self.main_frame, text=f"Create New Task in Project: {self.project_key}",
                                       font=FONT_MONO_BOLD, text_color=TERMINAL_GREEN)
        self.info_label.pack(pady=(0, 10))

        self.type_label = ctk.CTkLabel(self.main_frame, text="Issue Type:", anchor='w', font=FONT_MONO_NORMAL,
                                       text_color=TEXT_COLOR_NORMAL)
        self.type_label.pack(fill='x', pady=(5, 2))
        self.type_combobox = ctk.CTkComboBox(
            self.main_frame, values=self.issue_types, font=FONT_MONO_NORMAL,
            dropdown_font=FONT_MONO_NORMAL,
            corner_radius=0, fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            border_width=1, border_color=BORDER_COLOR,
            button_color=TERMINAL_GREEN, button_hover_color=TERMINAL_GREEN_BRIGHT,
            dropdown_fg_color=WIDGET_BACKGROUND, dropdown_hover_color=HOVER_COLOR_BTN,
            dropdown_text_color=TEXT_COLOR_NORMAL, state='readonly'
        )
        self.type_combobox.pack(fill='x')
        if self.issue_types:
            self.type_combobox.set(self.issue_types[0])
        else:
            self.type_combobox.set("NO TYPES FOUND")
            self.type_combobox.configure(state='disabled')

        self.summary_label = ctk.CTkLabel(self.main_frame, text="Summary:", anchor='w', font=FONT_MONO_NORMAL,
                                          text_color=TEXT_COLOR_NORMAL)
        self.summary_label.pack(fill='x', pady=(10, 2))
        self.summary_entry = ctk.CTkEntry(
            self.main_frame, font=FONT_MONO_NORMAL, corner_radius=0,
            fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            placeholder_text_color=TEXT_COLOR_DIM, border_width=1, border_color=BORDER_COLOR,
            placeholder_text="enter task summary >"
        )
        self.summary_entry.pack(fill='x')
        self.summary_entry.bind("<Return>", self._on_create)

        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(pady=(15, 0), fill='x')
        self.button_frame.grid_columnconfigure((0, 1), weight=1)

        self.create_button = ctk.CTkButton(
            self.button_frame, text="CREATE", font=FONT_MONO_BOLD,
            command=self._on_create,
            fg_color=STATUS_GREEN, text_color=BACKGROUND_COLOR, hover_color=TERMINAL_GREEN_BRIGHT,
            corner_radius=0
        )
        self.create_button.grid(row=0, column=0, padx=(0, 5), sticky='ew')
        if not self.issue_types:
            self.create_button.configure(state='disabled')

        self.cancel_button = ctk.CTkButton(
            self.button_frame, text="CANCEL", font=FONT_MONO_BOLD,
            command=self.destroy,
            fg_color=TEXT_COLOR_DIM, text_color=BACKGROUND_COLOR, hover_color=HOVER_COLOR_BTN,
            corner_radius=0
        )
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), sticky='ew')

        self.summary_entry.focus_set()

    def _on_create(self, event=None):
        summary = self.summary_entry.get().strip()
        issue_type = self.type_combobox.get()

        if not issue_type or issue_type == "NO TYPES FOUND":
            messagebox.showerror("Error", "No valid issue type selected.", parent=self)
            return
        if not summary:
            messagebox.showwarning("Input Error", "Task summary cannot be empty.", parent=self)
            self.summary_entry.focus_set()
            return

        print(
            f"Attempting creation from dialog: Summary='{summary}', Type='{issue_type}', Project='{self.project_key}'")

        new_issue_key = self.parent_gui.create_jira_issue(summary, issue_type, labels_list=None)

        if new_issue_key:
            print(f"Task {new_issue_key} created successfully via dialog.")
            messagebox.showinfo("Success", f"Task {new_issue_key} created successfully.", parent=self.parent_gui.root)
            self.destroy()
            self.parent_gui.refresh_task_list_window(self.parent_task_list_window)
        else:
            print("Task creation failed via dialog.")
            self.summary_entry.focus_set()


class GUI:
    def __init__(self):
        self.root = None
        self.jira_server = None
        self.jira_username = None
        self.jira_api_token = None
        self.auth = None
        self.headers = None
        self.projects = []
        self.project_keys = {}
        self.categories = []
        self.my_account_id = None
        self.selected_project_key = None
        self.current_task_name = ""
        self.current_jira_issue_key = None
        self.start_time = 0
        self.elapsed_time = 0
        self.timer_running = False
        self.selected_labels = set()

        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        config = None
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"Config loaded from {config_path}")
        except FileNotFoundError:
            print(f"ERROR: Config file not found: {config_path}")
            messagebox.showerror("Config Error", f"Config file not found:\n{config_path}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"ERROR: Invalid JSON in config file: {config_path}")
            messagebox.showerror("Config Error", f"Invalid JSON format in file:\n{config_path}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Unexpected error loading config from {config_path}: {e}")
            traceback.print_exc()
            messagebox.showerror("Config Error", f"Unexpected error loading configuration:\n{e}")
            sys.exit(1)

        try:
            self.jira_server = config['jira_server'].rstrip('/')
            self.jira_username = config['jira_username']
            self.jira_api_token = config['jira_api_token']
            if not all([self.jira_server, self.jira_username, self.jira_api_token]):
                raise ValueError(
                    "One or more required config values (jira_server, jira_username, jira_api_token) are empty.")
        except KeyError as e:
            missing_key = str(e).strip("'")
            print(f"ERROR: Missing key '{missing_key}' in config file: {config_path}")
            messagebox.showerror("Config Error", f"Missing key '{missing_key}' in config file:\n{config_path}")
            sys.exit(1)
        except ValueError as e:
            print(f"ERROR: {e} in file {config_path}")
            messagebox.showerror("Config Error", f"{e}\n\nCheck file: {config_path}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Unexpected error processing config: {e}")
            traceback.print_exc()
            messagebox.showerror("Config Error", f"Unexpected error processing configuration:\n{e}")
            sys.exit(1)

        self.auth = (self.jira_username, self.jira_api_token)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}

        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.configure(fg_color=BACKGROUND_COLOR)
        self.root.geometry("450x500")
        self.root.title("JIRA::FOCUS_v1.0")
        self.root.resizable(False, False)
        self.root.attributes('-alpha', 0.97)

        self.root.bind("<Control-q>", self.minimize_window)
        self.root.bind("<Control-Shift-q>", self.restore_window)

        self.label = ctk.CTkLabel(self.root, text="[[ JIRA FOCUS ]]", font=FONT_MONO_XLARGE, text_color=TERMINAL_GREEN)
        self.label.pack(padx=10, pady=(10, 15))

        self.project_label = ctk.CTkLabel(self.root, text="PROJECT:", font=FONT_MONO_LARGE,
                                          text_color=TEXT_COLOR_NORMAL)
        self.project_label.pack(anchor='w', padx=15)
        self.project_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.project_frame.pack(fill='x', padx=10, pady=(0, 5))
        self.project_combobox = ctk.CTkComboBox(
            self.project_frame, values=self.projects, font=FONT_MONO_NORMAL,
            dropdown_font=FONT_MONO_NORMAL, command=self.on_project_select,
            corner_radius=0, fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            border_width=1, border_color=BORDER_COLOR,
            button_color=TERMINAL_GREEN, button_hover_color=TERMINAL_GREEN_BRIGHT,
            dropdown_fg_color=WIDGET_BACKGROUND, dropdown_hover_color=HOVER_COLOR_BTN,
            dropdown_text_color=TEXT_COLOR_NORMAL, state='readonly'
        )
        self.project_combobox.pack(fill='x', expand=True)
        self.project_combobox.set("select project >")

        self.category_label = ctk.CTkLabel(self.root, text="ISSUE TYPE:", font=FONT_MONO_LARGE,
                                           text_color=TEXT_COLOR_NORMAL)
        self.category_display_label = ctk.CTkLabel(self.root, text="select issue type >", font=FONT_MONO_NORMAL,
                                                   text_color=TEXT_COLOR_NORMAL)


        self.issue_type_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.issue_type_frame.pack(fill='x', padx=10, pady=(5, 0))

        self.category_label = ctk.CTkLabel(self.issue_type_frame, text="ISSUE TYPE:", font=FONT_MONO_LARGE,
                                           text_color=TEXT_COLOR_NORMAL)
        self.category_label.grid(row=0, column=0, padx=(5, 5), sticky='w')

        self.category_display_label = ctk.CTkLabel(self.issue_type_frame, text="select issue type >",
                                                   font=FONT_MONO_NORMAL,
                                                   text_color=TEXT_COLOR_NORMAL)
        self.category_display_label.grid(row=0, column=1, padx=(0, 5),
                                         sticky='w')



        self.task_label = ctk.CTkLabel(self.root, text="TASK SUMMARY:", font=FONT_MONO_LARGE,
                                       text_color=TEXT_COLOR_NORMAL)
        self.task_label.pack(anchor='w', padx=15, pady=(5, 0))

        self.task_entry = ctk.CTkEntry(
            self.root, font=FONT_MONO_NORMAL, corner_radius=0,
            fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            placeholder_text_color=TEXT_COLOR_DIM, border_width=1, border_color=BORDER_COLOR,
            placeholder_text="enter task summary here >",
            state='disabled'
        )
        self.task_entry.pack(fill='x', padx=10, pady=(0, 10))

        self.action_buttons_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.action_buttons_frame.pack(fill='x', padx=10, pady=5)
        self.action_buttons_frame.grid_columnconfigure((0, 1), weight=1)

        self.edit_labels_button = ctk.CTkButton(
            self.action_buttons_frame, text="LABELS [0]", font=FONT_MONO_BOLD,
            command=self.open_label_editor_window,
            corner_radius=0, fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            border_color=BORDER_COLOR, border_width=1, hover_color=HOVER_COLOR_BTN
        )
        self.edit_labels_button.grid(row=0, column=0, padx=(0, 5), sticky='ew')

        self.assign_me_button = ctk.CTkButton(
            self.action_buttons_frame, text="ASSIGN_TO_ME", font=FONT_MONO_BOLD,
            command=self.assign_to_me, state='disabled',
            corner_radius=0, fg_color=STATUS_BLUE, text_color=BACKGROUND_COLOR,
            hover_color="#00AADD"
        )
        self.assign_me_button.grid(row=0, column=1, padx=(5, 0), sticky='ew')

        self.list_button_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.list_button_frame.pack(fill='x', padx=10, pady=5)
        self.history_button = ctk.CTkButton(
            self.list_button_frame, text="LIST TASKS IN PROJECT", font=FONT_MONO_BOLD,
            command=self.show_task_list, corner_radius=0, state='disabled',
            fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            border_color=BORDER_COLOR, border_width=1, hover_color=HOVER_COLOR_BTN
        )
        self.history_button.pack(fill='x', expand=True)

        self.timer_buttonframe = ctk.CTkFrame(self.root, fg_color="transparent")
        self.timer_buttonframe.pack(fill='x', padx=10, pady=5)
        self.timer_buttonframe.grid_columnconfigure((0, 1), weight=1)

        self.bstart = ctk.CTkButton(
            self.timer_buttonframe, text='START_TIMER', font=FONT_MONO_BOLD,
            command=self.start_timer, state='disabled',
            fg_color=STATUS_GREEN, text_color=BACKGROUND_COLOR,
            hover_color=TERMINAL_GREEN_BRIGHT, corner_radius=0
        )
        self.bstart.grid(row=0, column=0, padx=(0, 5), sticky='ew')

        self.bstop = ctk.CTkButton(
            self.timer_buttonframe, text='STOP_TIMER', font=FONT_MONO_BOLD,
            command=self.stop_timer, state='disabled',
            fg_color=ERROR_RED, text_color=BACKGROUND_COLOR,
            hover_color="#FF4444", corner_radius=0
        )
        self.bstop.grid(row=0, column=1, padx=(5, 0), sticky='ew')

        self.timer_label = ctk.CTkLabel(self.root, text="TIME: 00:00:00", font=FONT_MONO_LARGE,
                                        text_color=TERMINAL_GREEN)
        self.timer_label.pack(pady=5)

        self.status_label = ctk.CTkLabel(self.root, text="CHANGE STATUS:", font=FONT_MONO_LARGE,
                                         text_color=TEXT_COLOR_NORMAL)
        self.status_label.pack(pady=(10, 0))
        self.status_buttonframe = ctk.CTkFrame(self.root, fg_color="transparent")
        self.status_buttonframe.pack(fill='x', padx=10, pady=5)
        self.status_buttonframe.grid_columnconfigure((0, 1, 2), weight=1)

        self.bstatus_todo = ctk.CTkButton(
            self.status_buttonframe, text='[ ] TO DO', font=FONT_MONO_BOLD,
            command=lambda: self.change_status_to("To Do"), state='disabled',
            fg_color=STATUS_BLUE, text_color=BACKGROUND_COLOR,
            hover_color="#00AADD", corner_radius=0
        )
        self.bstatus_todo.grid(row=0, column=0, padx=(0, 5), sticky='ew')

        self.bstatus_inprogress = ctk.CTkButton(
            self.status_buttonframe, text='[>] IN PROGRESS', font=FONT_MONO_BOLD,
            command=lambda: self.change_status_to("In Progress"), state='disabled',
            fg_color=STATUS_ORANGE, text_color=BACKGROUND_COLOR,
            hover_color="#FFCC33", corner_radius=0
        )
        self.bstatus_inprogress.grid(row=0, column=1, padx=(5, 5), sticky='ew')

        self.bstatus_done = ctk.CTkButton(
            self.status_buttonframe, text='[X] DONE', font=FONT_MONO_BOLD,
            command=lambda: self.change_status_to("Done"), state='disabled',
            fg_color=STATUS_GREEN, text_color=BACKGROUND_COLOR,
            hover_color=TERMINAL_GREEN_BRIGHT, corner_radius=0
        )
        self.bstatus_done.grid(row=0, column=2, padx=(5, 0), sticky='ew')

        self._fetch_my_account_id()
        self.load_projects_from_jira()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def _make_jira_request(self, method, endpoint, **kwargs):
        if not self.jira_server:
            print("!! ERROR: Jira server address not configured.")
            return {'success': False, 'error': 'Jira server address not configured.', 'status_code': None}

        url = f"{self.jira_server}/rest/api/3/{endpoint}"
        log_url = url.split('?')[0]

        log_data_summary = ""
        if 'data' in kwargs and method in ["POST", "PUT"]:
            try:
                json.loads(kwargs['data'])
                log_data_summary = " with JSON data"
            except (json.JSONDecodeError, TypeError):
                log_data_summary = " with data"
        print(f"--> JIRA_API: {method} {log_url}{log_data_summary}")

        try:
            response = requests.request(
                method, url,
                auth=self.auth,
                headers=self.headers,
                timeout=30,
                **kwargs
            )

            response.raise_for_status()

            if response.status_code == 204:
                print(f"<-- JIRA_API: {response.status_code} NO_CONTENT")
                return {'success': True, 'status_code': response.status_code}
            else:
                try:
                    data = response.json()
                    print(f"<-- JIRA_API: {response.status_code} OK (JSON)")
                    return {'success': True, 'status_code': response.status_code, 'data': data}
                except json.JSONDecodeError:
                    print(f"<-- JIRA_API: {response.status_code} OK (Non-JSON): {response.text[:100]}...")
                    is_success = 200 <= response.status_code < 300
                    return {'success': is_success, 'status_code': response.status_code, 'raw_response': response.text}

        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code if http_err.response is not None else 'N/A'
            response_text = http_err.response.text if http_err.response is not None else '<no response body>'
            error_message = f"!! HTTP Error {status_code} for {method} {log_url}: {http_err}"
            jira_error_details = ""
            try:
                if http_err.response is not None:
                    error_json = http_err.response.json()
                    jira_error_messages = error_json.get('errorMessages', [])
                    jira_errors = error_json.get('errors', {})
                    if jira_error_messages: jira_error_details += f"\nJira Messages: {jira_error_messages}"
                    if jira_errors: jira_error_details += f"\nJira Details: {jira_errors}"
                    error_message += jira_error_details
            except (json.JSONDecodeError, AttributeError):
                pass
            print(f"[API ERROR] {error_message}\nResponse Body: {response_text[:500]}...")
            return {'success': False, 'error': error_message, 'status_code': status_code, 'raw_response': response_text}

        except requests.exceptions.ConnectionError as conn_err:
            err_msg = f"!! Connection Error for {method} {log_url}: {conn_err}"
            print(f"[API ERROR] {err_msg}")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Connection Error",
                                     "Cannot connect to Jira server.\nCheck server address and network connection.",
                                     parent=self.root)
            return {'success': False, 'error': err_msg, 'status_code': None}
        except requests.exceptions.Timeout as timeout_err:
            err_msg = f"!! Timeout Error for {method} {log_url}: {timeout_err}"
            print(f"[API ERROR] {err_msg}")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Timeout", "Jira API request timed out.", parent=self.root)
            return {'success': False, 'error': err_msg, 'status_code': None}
        except requests.exceptions.RequestException as req_err:
            err_msg = f"!! Request Exception for {method} {log_url}: {req_err}"
            print(f"[API ERROR] {err_msg}")
            traceback.print_exc()
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Request Error", f"An unexpected request error occurred: {req_err}",
                                     parent=self.root)
            return {'success': False, 'error': err_msg, 'status_code': None}

    def _fetch_my_account_id(self):
        print("Fetching user info (accountId)...")
        result = self._make_jira_request("GET", "myself")
        if result and result['success'] and 'data' in result and 'accountId' in result['data']:
            self.my_account_id = result['data']['accountId']
            print(f">> My accountId: {self.my_account_id}")
        else:
            self.my_account_id = None
            print("!! ERROR: Failed to fetch user accountId.")
            error_details = result.get('error', 'No details') if result else 'No response'
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showwarning("User Data Error",
                                       f"Could not fetch your Jira user ID.\n'Assign To Me' disabled.\nError: {error_details[:150]}...",
                                       parent=self.root)
        if hasattr(self, 'root') and self.root.winfo_exists():
            self._update_action_button_states()

    def _format_seconds_to_jira_duration(self, seconds):
        seconds = int(seconds)
        if seconds <= 0: return "0m"

        total_minutes = (seconds + 59) // 60

        if total_minutes <= 0: return "1m"

        h, m = divmod(total_minutes, 60)

        parts = []
        if h > 0: parts.append(f"{h}h")
        if m > 0: parts.append(f"{m}m")

        formatted_duration = " ".join(parts)
        return formatted_duration if formatted_duration else "1m"

    def load_projects_from_jira(self):
        print("Fetching projects from Jira...")
        result = self._make_jira_request("GET", "project/search")

        self.projects = []
        self.project_keys = {}

        if result and result['success'] and 'data' in result and 'values' in result['data']:
            all_projects = result['data']['values']
            self.projects = sorted([f"{p['name']} ({p['key']})" for p in all_projects if 'name' in p and 'key' in p])
            self.project_keys = {f"{p['name']} ({p['key']})": p['key'] for p in all_projects if
                                 'name' in p and 'key' in p}
            print(f"Loaded {len(self.projects)} projects.")
        else:
            print("Failed to load projects or no projects found.")
            if result and not result['success'] and hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("API Project Error",
                                     f"Could not fetch project list.\nDetails: {result.get('error', 'N/A')}",
                                     parent=self.root)

        if hasattr(self, 'project_combobox') and self.project_combobox.winfo_exists():
            self.project_combobox.configure(values=self.projects)
            self.project_combobox.set("select project >" if self.projects else "no projects/API error")

        self.selected_project_key = None
        self.categories = []

        if hasattr(self, 'category_display_label') and self.category_display_label.winfo_exists():
            self.category_display_label.configure(text=" ... ")
        if hasattr(self, 'task_entry') and self.task_entry.winfo_exists():
            self.task_entry.delete(0, "end")
            self.task_entry.configure(placeholder_text="enter task summary here >")
        self.selected_labels = set()
        if hasattr(self, 'edit_labels_button') and self.edit_labels_button.winfo_exists():
            self.edit_labels_button.configure(text="LABELS [0]")
        self.current_jira_issue_key = None
        self.current_task_name = ""

        if hasattr(self, 'root') and self.root.winfo_exists():
            self._update_action_button_states()

    def on_project_select(self, choice):
        if self.timer_running:
            messagebox.showwarning("Timer Active", "Stop the timer before changing project.", parent=self.root)
            current_display = next(
                (disp for disp, key in self.project_keys.items() if key == self.selected_project_key), None)
            if current_display and hasattr(self, 'project_combobox') and self.project_combobox.winfo_exists():
                self.project_combobox.set(current_display)
            return

        selected_key_candidate = self.project_keys.get(choice)

        if selected_key_candidate != self.selected_project_key:
            self.selected_project_key = selected_key_candidate
            if self.selected_project_key:
                print(f"Project selected: {choice} (Key: {self.selected_project_key})")
                if hasattr(self, 'task_entry') and self.task_entry.winfo_exists():
                    self.task_entry.delete(0, "end")
                    self.task_entry.configure(placeholder_text="enter task summary here >")
                self.current_jira_issue_key = None
                self.current_task_name = ""
                self.selected_labels = set()
                if hasattr(self, 'edit_labels_button') and self.edit_labels_button.winfo_exists():
                    self.edit_labels_button.configure(text="LABELS [0]")
                self.load_categories_from_jira()
            else:
                print(f"Invalid project selection or reset: {choice}")
                self.selected_project_key = None
                self.categories = []
                if hasattr(self, 'category_display_label') and self.category_display_label.winfo_exists():
                    self.category_display_label.configure(text="select project first >")
                if hasattr(self, 'task_entry') and self.task_entry.winfo_exists():
                    self.task_entry.delete(0, "end")
                self.selected_labels = set()
                if hasattr(self, 'edit_labels_button') and self.edit_labels_button.winfo_exists():
                    self.edit_labels_button.configure(text="LABELS [0]")
                self.current_jira_issue_key = None
                self.current_task_name = ""

            if hasattr(self, 'root') and self.root.winfo_exists():
                self._update_action_button_states()

    def load_categories_from_jira(self):
        self.categories = []

        if hasattr(self, 'category_display_label') and self.category_display_label.winfo_exists():
            self.category_display_label.configure(text="loading types...")

        if not self.selected_project_key:
            print("No project selected, cannot load issue types.")
            if hasattr(self, 'category_display_label') and self.category_display_label.winfo_exists():
                self.category_display_label.configure(text="select project first >")
            if hasattr(self, 'root') and self.root.winfo_exists(): self._update_action_button_states()
            return

        print(f"Fetching issue types for project: {self.selected_project_key}...")
        endpoint = f"issue/createmeta?projectKeys={self.selected_project_key}&expand=projects.issuetypes"
        result = self._make_jira_request("GET", endpoint)

        loaded_categories = []
        if result and result['success'] and 'data' in result and result['data'].get('projects'):
            project_meta_list = result['data'].get('projects', [])
            project_meta = next((p for p in project_meta_list if p.get('key') == self.selected_project_key), None)
            if project_meta:
                issue_types = project_meta.get('issuetypes', [])
                loaded_categories = sorted(
                    [it['name'] for it in issue_types if not it.get('subtask', False) and 'name' in it])
                if not loaded_categories:
                    print(f"Warning: No standard issue types found for {self.selected_project_key}.")
                else:
                    print(f"Loaded {len(loaded_categories)} standard issue types for {self.selected_project_key}.")
            else:
                print(f"Warning: No metadata found for project {self.selected_project_key} in API response.")
        else:
            print(f"Failed to load issue type metadata for {self.selected_project_key}.")
            if result and not result['success'] and hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("API Issue Type Error",
                                     f"Could not fetch issue types.\nDetails: {result.get('error', 'N/A')}",
                                     parent=self.root)

        self.categories = loaded_categories
        if hasattr(self, 'category_display_label') and self.category_display_label.winfo_exists():
            if not self.categories:
                self.category_display_label.configure(text="no types/error")
            else:
                self.category_display_label.configure(text=self.categories[0])

        if hasattr(self, 'root') and self.root.winfo_exists():
            self._update_action_button_states()

    def create_jira_issue(self, task_name, issue_type_name, labels_list=None):
        if not self.selected_project_key:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("Error", "No project selected.",
                                                                                        parent=self.root)
            return None
        if not task_name:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("Error",
                                                                                        "Task summary cannot be empty.",
                                                                                        parent=self.root)
            return None
        if not issue_type_name or issue_type_name.startswith(("select ", "loading", "no types")):
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("Error",
                                                                                        "Invalid issue type selected.",
                                                                                        parent=self.root)
            return None

        print(f"Creating issue in {self.selected_project_key}: Type='{issue_type_name}', Summary='{task_name}'")
        if labels_list: print(f"  with labels: {labels_list}")

        summary = task_name.strip()
        description_text = f"Task created via JIRA Focus: {summary}"
        adf_description = {"type": "doc", "version": 1,
                           "content": [{"type": "paragraph", "content": [{"type": "text", "text": description_text}]}]}

        issue_data = {
            "fields": {
                "project": {"key": self.selected_project_key},
                "summary": summary,
                "description": adf_description,
                "issuetype": {"name": issue_type_name},
            }
        }

        if labels_list:
            valid_labels = [lbl for lbl in labels_list if lbl and not re.search(r"\s", lbl)]
            if valid_labels:
                issue_data["fields"]["labels"] = valid_labels
                print(f"  Adding valid labels: {valid_labels}")

        result = self._make_jira_request("POST", "issue", data=json.dumps(issue_data))

        if result and result['success'] and 'data' in result and 'key' in result['data']:
            issue_key = result['data']['key']
            print(f">> Successfully created Jira issue: {issue_key}")
            return issue_key
        else:
            print("!! Failed to create Jira issue.")
            error_msg = "Failed to create Jira issue."
            if result and result.get('error'):
                error_msg += f"\nAPI Error: {result['error']}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', []);
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nDetails: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result and result.get('raw_response'):
                error_msg += f"\nServer Response ({result.get('status_code')}): {result['raw_response'][:200]}..."
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Issue Creation Error", error_msg, parent=self.root)
            return None

    def log_work_to_jira(self, issue_key, elapsed_seconds):
        if not issue_key:
            print("Cannot log time: missing issue key.")
            return False

        if elapsed_seconds <= 0:
            print(f"Work duration <= 0 ({elapsed_seconds}s). Time not logged.")
            return True

        print(f"Logging work for task: {issue_key}")
        jira_duration_string = self._format_seconds_to_jira_duration(elapsed_seconds)
        if jira_duration_string == "0m": jira_duration_string = "1m"

        print(f"Formatted time for Jira: {jira_duration_string} (from {elapsed_seconds}s)")

        comment_text = f"Worklog ({int(elapsed_seconds)}s -> {jira_duration_string}) added via JIRA Focus."
        adf_comment = {"type": "doc", "version": 1,
                       "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment_text}]}]}

        worklog_data = {"timeSpent": jira_duration_string, "comment": adf_comment}

        endpoint = f"issue/{issue_key}/worklog"
        result = self._make_jira_request("POST", endpoint, data=json.dumps(worklog_data))

        if result and result['success'] and 'data' in result and 'id' in result['data']:
            print(f">> Successfully logged work ({jira_duration_string}) for {issue_key}.")
            return True
        else:
            print(f"!! Failed to log work for {issue_key}.")
            error_msg = f"Failed to log work for {issue_key}."
            if result and result.get('error'):
                error_msg += f"\nAPI Error: {result.get('error')}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', []);
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nDetails: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result and result.get('raw_response'):
                error_msg += f"\nServer Response ({result.get('status_code')}): {result['raw_response'][:200]}..."
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Worklog Error", error_msg, parent=self.root)
            return False

    def _get_available_transitions(self, issue_key):
        if not issue_key: return None
        print(f"Fetching transitions for task: {issue_key}")
        endpoint = f"issue/{issue_key}/transitions"
        result = self._make_jira_request("GET", endpoint)

        if result and result['success'] and 'data' in result and 'transitions' in result['data']:
            transitions = result['data']['transitions']
            print(
                f"  Found transitions: {[t.get('name', 'N/A') + ' (ID:' + t.get('id', '?') + ' -> ' + t.get('to', {}).get('name', '??') + ')' for t in transitions]}")
            return transitions
        else:
            print(f"!! Failed to get transitions for {issue_key} or none available.")
            if result and not result['success']:
                print(f"   Error details: {result.get('error', 'N/A')}")
            elif result and result['success']:
                print("   No transitions available or unexpected response structure.")
            return None

    def _transition_issue(self, issue_key, target_status_name):
        if not issue_key:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("Error",
                                                                                        "Select/create task first.",
                                                                                        parent=self.root)
            return False

        transitions = self._get_available_transitions(issue_key)

        if transitions is None:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("Transition Error",
                                                                                        f"Failed to get transitions for {issue_key}.",
                                                                                        parent=self.root)
            return False
        if not transitions:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showwarning("No Transitions",
                                                                                          f"No status changes possible for {issue_key} from current state.",
                                                                                          parent=self.root)
            return False

        target_transition_id = None
        target_status_name_lower = target_status_name.lower()
        found_transition_name = "N/A"
        for t in transitions:
            to_status_name = t.get('to', {}).get('name', '').lower()
            if to_status_name == target_status_name_lower:
                target_transition_id = t.get('id')
                found_transition_name = t.get('name', 'N/A')
                print(
                    f"  Found transition: '{found_transition_name}' (ID: {target_transition_id}) to status '{target_status_name}'.")
                break

        if not target_transition_id:
            available_names = sorted(list(set([t.get('to', {}).get('name', 'N/A') for t in transitions])))
            print(f"!! Transition to '{target_status_name}' not found for {issue_key}.")
            print(f"   Available targets: {available_names}")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Transition Error",
                                     f"Cannot change status to '{target_status_name}'.\nAvailable: {', '.join(available_names)}",
                                     parent=self.root)
            return False

        print(f"Executing transition '{found_transition_name}' (ID: {target_transition_id}) for {issue_key}...")
        endpoint = f"issue/{issue_key}/transitions"
        payload = {"transition": {"id": target_transition_id}}
        result = self._make_jira_request("POST", endpoint, data=json.dumps(payload))

        if result and result['success'] and result.get('status_code') == 204:
            print(f">> Successfully changed status of {issue_key} to '{target_status_name}'.")
            return True
        else:
            print(f"!! Failed to execute transition ID {target_transition_id} for {issue_key}.")
            error_msg = f"Error changing status of {issue_key} to '{target_status_name}'."
            if result and result.get('error'):
                error_msg += f"\nAPI Error: {result['error']}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', []);
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nDetails: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result:
                error_msg += f"\nServer response code {result.get('status_code', 'N/A')}"
            if result and result.get(
                'raw_response'): error_msg += f"\nResponse: {result.get('raw_response', '')[:200]}..."
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Transition Error", error_msg, parent=self.root)
            return False

    def change_status_to(self, target_status_name):
        print(f"--- Requesting status change to: {target_status_name} ---")
        if not self.current_jira_issue_key:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showwarning("No Task", "Select a task first.", parent=self.root)
            return
        self._transition_issue(self.current_jira_issue_key, target_status_name)

    def _update_action_button_states(self):
        if not hasattr(self, 'root') or not self.root.winfo_exists(): return

        project_selected = bool(self.selected_project_key)
        task_selected = bool(self.current_jira_issue_key)
        category_selected = False

        if hasattr(self, 'category_display_label') and self.category_display_label.winfo_exists():
            current_cat = self.category_display_label.cget("text")
            category_selected = bool(current_cat and not current_cat.startswith(("select ", "loading", "no types")))
        task_summary_present = False
        if hasattr(self, 'task_entry') and self.task_entry.winfo_exists():
            task_summary_present = bool(self.task_entry.get().strip())

        can_start = project_selected and category_selected and task_summary_present and not self.timer_running
        can_stop = self.timer_running
        can_change_status = task_selected and not self.timer_running
        can_assign = task_selected and bool(self.my_account_id) and not self.timer_running
        can_edit_labels = (project_selected or task_selected) and not self.timer_running
        can_list = project_selected and not self.timer_running

        status_state = 'normal' if can_change_status else 'disabled'
        if hasattr(self, 'bstatus_todo'): self.bstatus_todo.configure(state=status_state)
        if hasattr(self, 'bstatus_inprogress'): self.bstatus_inprogress.configure(state=status_state)
        if hasattr(self, 'bstatus_done'): self.bstatus_done.configure(state=status_state)

        assign_state = 'normal' if can_assign else 'disabled'
        if hasattr(self, 'assign_me_button'): self.assign_me_button.configure(state=assign_state)

        labels_state = 'normal' if can_edit_labels else 'disabled'
        if hasattr(self, 'edit_labels_button'): self.edit_labels_button.configure(state=labels_state)

        list_state = 'normal' if can_list else 'disabled'
        if hasattr(self, 'history_button'): self.history_button.configure(state=list_state)

        start_state = 'normal' if can_start else 'disabled'
        stop_state = 'normal' if can_stop else 'disabled'
        if hasattr(self, 'bstart'): self.bstart.configure(state=start_state)
        if hasattr(self, 'bstop'): self.bstop.configure(state=stop_state)

        input_state = 'disabled' if self.timer_running else 'normal'
        combo_state = 'disabled' if self.timer_running else 'readonly'
        if hasattr(self, 'project_combobox'): self.project_combobox.configure(state=combo_state)


    def assign_to_me(self):
        print("--- Requesting assign task to me ---")
        if self.timer_running:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showwarning("Timer Active",
                                                                                          "Stop timer before assigning.",
                                                                                          parent=self.root)
            return
        if not self.current_jira_issue_key:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("No Task", "Select task first.",
                                                                                        parent=self.root)
            return
        if not self.my_account_id:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("User ID Error",
                                                                                        "Cannot assign: User ID missing.",
                                                                                        parent=self.root)
            print("Assign failed: My accountId missing.")
            return

        print(f"Assigning {self.current_jira_issue_key} to user: {self.my_account_id}")
        endpoint = f"issue/{self.current_jira_issue_key}/assignee"
        payload = {"accountId": self.my_account_id}
        result = self._make_jira_request("PUT", endpoint, data=json.dumps(payload))

        if result and result['success'] and result.get('status_code') in [200, 204]:
            print(f">> Successfully assigned {self.current_jira_issue_key} to you.")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showinfo("Success", f"Task {self.current_jira_issue_key} assigned to you.", parent=self.root)
        else:
            print(f"!! Failed to assign {self.current_jira_issue_key} to you.")
            error_msg = f"Error assigning task {self.current_jira_issue_key}."
            if result and result.get('error'):
                error_msg += f"\nAPI Error: {result['error']}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', []);
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nDetails: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result and result.get('raw_response'):
                error_msg += f"\nServer Response ({result.get('status_code')}): {result['raw_response'][:200]}..."
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Assignment Error", error_msg, parent=self.root)

    def start_timer(self):
        if not hasattr(self, 'root') or not self.root.winfo_exists(): return
        if self.timer_running:
            print("Timer already running.")
            return

        self.current_task_name = self.task_entry.get().strip() if hasattr(self, 'task_entry') else ""
        selected_issue_type = None

        if hasattr(self, 'category_display_label'):
            selected_issue_type = self.category_display_label.cget("text")

        selected_project_display = self.project_combobox.get() if hasattr(self, 'project_combobox') else ""

        if not self.selected_project_key:
            if hasattr(self, 'root'): messagebox.showerror("Error", "No project selected.", parent=self.root)
            return
        if not selected_issue_type or selected_issue_type.startswith(("select ", "loading", "no types")):
            if hasattr(self, 'root'): messagebox.showerror("Error", f"Select valid issue type.", parent=self.root)
            return
        if not self.current_task_name:
            if hasattr(self, 'root'): messagebox.showerror("Error", "Task summary empty.", parent=self.root)
            return

        expected_key = self.project_keys.get(selected_project_display)
        if not expected_key or expected_key != self.selected_project_key:
            if hasattr(self, 'root'): messagebox.showerror("Project Mismatch",
                                                           f"Project inconsistency. Re-select project.",
                                                           parent=self.root)
            self.load_projects_from_jira()
            return

        issue_key_to_use = self.current_jira_issue_key

        if not issue_key_to_use:
            print("No existing task loaded, creating new Jira issue...")
            final_labels = sorted(list(self.selected_labels))
            print(f"Using labels for new task: {final_labels}")

            new_issue_key = self.create_jira_issue(self.current_task_name, selected_issue_type, final_labels)

            if new_issue_key:
                issue_key_to_use = new_issue_key
                self.current_jira_issue_key = new_issue_key
                print(f"Current task set to new issue: {self.current_jira_issue_key}")
                self.selected_labels = set()
                if hasattr(self, 'edit_labels_button'): self.edit_labels_button.configure(text="LABELS [0]")
            else:
                print("Timer cannot start: Jira issue creation failed.")
                return
        else:
            print(f"Using existing task: {issue_key_to_use}")

        if issue_key_to_use:
            self.current_jira_issue_key = issue_key_to_use
            self.start_time = time.time()
            self.elapsed_time = 0
            self.timer_running = True
            print(f"Timer started for: {self.current_jira_issue_key} - '{self.current_task_name}'")

            if hasattr(self, 'bstart'): self.bstart.configure(text='TIMER_RUNNING...')

            self.update_timer()
            self._update_action_button_states()
        else:
            print("CRITICAL ERROR: No Jira issue key available. Timer not started.")
            if hasattr(self, 'root'): messagebox.showerror("Internal Error", "Failed to get Jira issue key.",
                                                           parent=self.root)

    def stop_timer(self):
        if not self.timer_running:
            print("Timer not running.")
            return

        self.timer_running = False
        if self.start_time > 0:
            self.elapsed_time = time.time() - self.start_time
        else:
            self.elapsed_time = 0
            print("Warning: Invalid start_time on stop.")

        elapsed_seconds = int(self.elapsed_time)
        print(f"Timer stopped. Elapsed: {elapsed_seconds}s.")

        log_success = False
        if self.current_jira_issue_key:
            if elapsed_seconds > 0:
                log_success = self.log_work_to_jira(self.current_jira_issue_key, elapsed_seconds)
            else:
                print("Elapsed time zero, skipping work log.")
                log_success = True
        else:
            print("Warning: No Jira issue key associated. Cannot log time.")
            log_success = True

        if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
            if elapsed_seconds > 0:
                last_log_str = self._format_seconds_to_jira_duration(self.elapsed_time)
                status = "LAST" if log_success else "LOG FAIL"
                self.timer_label.configure(text=f"{status}: {last_log_str} ({elapsed_seconds}s raw)")
            else:
                self.timer_label.configure(text=f"TIME: 00:00:00 (0s)")

        if hasattr(self, 'bstart'): self.bstart.configure(text='START_TIMER')

        self._update_action_button_states()
        self.start_time = 0

    def update_timer(self):
        if self.timer_running and hasattr(self, 'root') and self.root.winfo_exists():
            if self.start_time > 0:
                current_elapsed = time.time() - self.start_time
                h, rem = divmod(int(current_elapsed), 3600)
                m, s = divmod(rem, 60)
                time_string = f"TIME: {h:02d}:{m:02d}:{s:02d}"

                if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
                    self.timer_label.configure(text=time_string)

                if self.timer_running:
                    self.root.after(1000, self.update_timer)
            else:
                print("Warning: Timer update called but start_time invalid.")
                if hasattr(self, 'timer_label'): self.timer_label.configure(text="TIME: ERROR")
                self.timer_running = False
        elif not self.timer_running:
            pass
        else:
            print("Timer loop stopping: main window gone.")
            self.timer_running = False

    def open_label_editor_window(self):
        if self.timer_running:
            if hasattr(self, 'root'): messagebox.showwarning("Timer Active", "Stop timer before editing labels.",
                                                             parent=self.root)
            return
        if not self.selected_project_key and not self.current_jira_issue_key:
            if hasattr(self, 'root'): messagebox.showerror("Error", "Select project or load task first.",
                                                           parent=self.root)
            return

        if hasattr(self, 'root') and self.root.winfo_exists():
            editor = LabelEditorWindow(self)
            editor.focus_force()
        else:
            print("!! ERROR: Cannot open label editor, main window missing.")

    def show_task_list(self):
        if not hasattr(self, 'root') or not self.root.winfo_exists(): return
        if self.timer_running:
            if hasattr(self, 'root'): messagebox.showinfo("Timer Active", "Stop timer before Browse tasks.",
                                                          parent=self.root)
            return
        if not self.selected_project_key:
            if hasattr(self, 'root'): messagebox.showerror("No Project", "Select project first.", parent=self.root)
            return

        task_window = ctk.CTkToplevel(self.root)
        task_window.configure(fg_color=BACKGROUND_COLOR)
        task_window.title(f"TASK_LIST::{self.selected_project_key}")
        task_window.geometry("900x550")
        task_window.transient(self.root)
        task_window.grab_set()
        task_window.attributes('-alpha', 0.97)
        try:
            main_x, main_y = self.root.winfo_x(), self.root.winfo_y()
            main_w, main_h = self.root.winfo_width(), self.root.winfo_height()
            win_w, win_h = 900, 550
            task_window.geometry(
                f"{win_w}x{win_h}+{main_x + (main_w // 2) - (win_w // 2)}+{main_y + (main_h // 2) - (win_h // 2)}")
        except Exception as e:
            print(f"Could not center task list: {e}")

        scroll_frame = ctk.CTkScrollableFrame(
            task_window, label_text=f"RECENT TASKS IN PROJECT: {self.selected_project_key}",
            label_font=FONT_MONO_BOLD, label_text_color=TERMINAL_GREEN,
            fg_color=WIDGET_BACKGROUND, corner_radius=0, border_width=1, border_color=BORDER_COLOR,
            scrollbar_button_color=TERMINAL_GREEN, scrollbar_button_hover_color=TERMINAL_GREEN_BRIGHT
        )
        scroll_frame.pack(fill='both', padx=10, pady=(5, 0), expand=True)

        loading = ctk.CTkLabel(scroll_frame, text="fetching tasks...", font=FONT_MONO_NORMAL,
                               text_color=TEXT_COLOR_NORMAL)
        loading.pack(pady=20)
        if hasattr(self, 'root'): self.root.update_idletasks()

        print(f"Fetching tasks for project {self.selected_project_key}...")
        jql = f'project = "{self.selected_project_key}" AND status NOT IN ("Done", "Resolved", "Canceled", "Closed") ORDER BY updated DESC'
        fields = "summary,status,issuetype,worklog,labels,assignee"
        max_res = 50
        endpoint = f"search?jql={requests.utils.quote(jql)}&fields={fields}&maxResults={max_res}"
        result = self._make_jira_request("GET", endpoint)

        if loading.winfo_exists(): loading.destroy()

        for widget in scroll_frame.winfo_children():
            if isinstance(widget, (ctk.CTkLabel, ctk.CTkButton, ctk.CTkFrame)):
                if widget.winfo_exists(): widget.destroy()

        if result and result['success'] and 'data' in result and 'issues' in result['data']:
            issues = result['data']['issues']
            total = result['data'].get('total', len(issues))
            print(f"Found {len(issues)} tasks (displaying max {max_res}/{total}) for {self.selected_project_key}.")

            if not issues:
                ctk.CTkLabel(scroll_frame, text="// no tasks found", font=FONT_MONO_NORMAL,
                             text_color=TEXT_COLOR_DIM).pack(pady=10)
            else:
                for i, issue in enumerate(issues):
                    try:
                        key = issue.get('key', 'NO-KEY')
                        flds = issue.get('fields', {})
                        summ = flds.get('summary', '<no summary>')
                        stat = flds.get('status', {}).get('name', 'N/A')
                        itype = flds.get('issuetype', {}).get('name', 'N/A')
                        lbls = flds.get('labels', [])
                        assignee = flds.get('assignee')
                        assignee_name = assignee.get('displayName', '<unassigned>') if assignee else '<unassigned>'
                        time_secs = sum(
                            wl.get('timeSpentSeconds', 0) for wl in flds.get('worklog', {}).get('worklogs', []))
                        time_str = self._format_seconds_to_jira_duration(time_secs) if time_secs > 0 else "0m"
                        lbl_str = f" {{{', '.join(lbls)}}}" if lbls else ""
                        summ_disp = summ[:45] + ('...' if len(summ) > 45 else '')
                        disp_txt = f"[{key}] {summ_disp} ({stat}) <{assignee_name}>{lbl_str} Σ:{time_str}"

                        tframe = ctk.CTkFrame(scroll_frame, fg_color="transparent", corner_radius=0)
                        tframe.pack(fill='x', pady=1, padx=0)
                        tbtn = ctk.CTkButton(
                            tframe, text=disp_txt, font=FONT_MONO_NORMAL, anchor='w', corner_radius=0,
                            fg_color=WIDGET_BACKGROUND if i % 2 == 0 else "#282828",
                            text_color=TEXT_COLOR_NORMAL, hover_color=HOVER_COLOR_BTN,
                            command=lambda s=summ, k=key, t=itype, l=set(lbls), a=assignee,
                                           win=task_window: self.select_task(s, k, t, l, a, win)
                        )
                        tbtn.pack(fill='x', expand=True)
                    except Exception as issue_e:
                        print(f"Error rendering task {issue.get('key', 'N/A')}: {issue_e}")
                        traceback.print_exc()
                        err_frame = ctk.CTkFrame(scroll_frame, fg_color="#400000", corner_radius=0)
                        err_frame.pack(fill='x', pady=1, padx=0)
                        ctk.CTkLabel(err_frame, text=f"!! Error rendering {issue.get('key', 'N/A')} !!",
                                     font=FONT_MONO_SMALL, text_color=ERROR_RED).pack(pady=2, padx=5, anchor='w')
        else:
            print("Error fetching tasks or no results.")
            err_text = "!! ERROR FETCHING TASKS / NO RESULTS !!"
            if result and not result['success']: err_text += f"\nDETAILS: {result.get('error', 'N/A')[:200]}..."
            ctk.CTkLabel(scroll_frame, text=err_text, font=FONT_MONO_NORMAL, text_color=ERROR_RED, wraplength=700).pack(
                pady=10)

        btn_frame = ctk.CTkFrame(task_window, fg_color="transparent")
        btn_frame.pack(fill='x', padx=10, pady=(5, 10))
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        refresh = ctk.CTkButton(
            btn_frame, text="REFRESH", font=FONT_MONO_BOLD, corner_radius=0,
            command=lambda win=task_window: self.refresh_task_list_window(win),
            fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            border_color=BORDER_COLOR, border_width=1, hover_color=HOVER_COLOR_BTN
        )
        refresh.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        create = ctk.CTkButton(
            btn_frame, text="CREATE TASK", font=FONT_MONO_BOLD, corner_radius=0,
            command=lambda win=task_window: self._create_new_task_from_list_window(win),
            fg_color=WIDGET_BACKGROUND, text_color=TEXT_COLOR_NORMAL,
            border_color=BORDER_COLOR, border_width=1, hover_color=HOVER_COLOR_BTN
        )
        create.grid(row=0, column=1, padx=(5, 5), sticky="ew")

        close = ctk.CTkButton(
            btn_frame, text="CLOSE", font=FONT_MONO_BOLD, corner_radius=0,
            command=task_window.destroy,
            fg_color=TEXT_COLOR_DIM, text_color=BACKGROUND_COLOR, hover_color=HOVER_COLOR_BTN
        )
        close.grid(row=0, column=2, padx=(5, 0), sticky="ew")

        task_window.protocol("WM_DELETE_WINDOW", task_window.destroy)

    def _create_new_task_from_list_window(self, parent_window):
        print("Create Task requested from Task List...")

        if not self.selected_project_key:
            messagebox.showerror("Error", "No project selected.", parent=parent_window)
            return
        if not self.categories:
            messagebox.showerror("Error", "Issue types not loaded.", parent=parent_window)
            return

        dialog = CreateTaskDialog(self, parent_window, self.selected_project_key, self.categories)
        dialog.focus_force()

    def refresh_task_list_window(self, window):
        print("Refreshing task list window...")
        if window and window.winfo_exists(): window.destroy()
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(100, self.show_task_list)

    def select_task(self, summary, issue_key, issue_type_name, labels_set, assignee_data, window):
        if not hasattr(self, 'root') or not self.root.winfo_exists():
            if window and window.winfo_exists(): window.destroy()
            return

        if self.timer_running:
            messagebox.showwarning("Timer Active", "Stop timer before selecting new task.",
                                   parent=window if window else self.root)
            if window and window.winfo_exists(): window.focus_force()
            return

        assignee_name = assignee_data.get('displayName', '<unassigned>') if assignee_data else '<unassigned>'
        print(f"Selected: [{issue_key}] {summary} (Type: {issue_type_name}, Assignee: {assignee_name})")

        if hasattr(self, 'task_entry'):
            self.task_entry.configure(state='normal')
            self.task_entry.delete(0, "end")
            self.task_entry.insert(0, summary)
            self.task_entry.configure(state='disabled')

        if hasattr(self, 'category_display_label'):
            if issue_type_name and issue_type_name in self.categories:
                self.category_display_label.configure(text=issue_type_name)
            elif self.categories:
                print(f"Warning: Type '{issue_type_name}' not in standard list. Defaulting.")
                self.category_display_label.configure(text=self.categories[0])
            else:
                self.category_display_label.configure(text="select type >")

        self.selected_labels = set()
        if hasattr(self, 'edit_labels_button'):
            self.edit_labels_button.configure(text=f"LABELS [{len(labels_set)}]")

        self.current_jira_issue_key = issue_key
        self.current_task_name = summary

        self._update_action_button_states()

        if window and window.winfo_exists(): window.destroy()

    def minimize_window(self, event=None):
        if self.root and self.root.winfo_exists():
            self.root.iconify()
            print("// Window minimized (Ctrl+Q)")

    def restore_window(self, event=None):
        if self.root and self.root.winfo_exists():
            self.root.deiconify()
            print("// Window restored (Ctrl+Shift+Q)")

    def on_closing(self):
        print("## Closing JIRA Focus ##")
        if self.timer_running:
            print("!! WARNING: Timer running on close! Time not logged. !!")
            self.timer_running = False

        if self.root and self.root.winfo_exists(): self.root.destroy()
        print(">> Application closed.")


if __name__ == "__main__":
    missing_libs = []
    try:
        import customtkinter
    except ImportError:
        missing_libs.append("customtkinter")
    try:
        import requests
    except ImportError:
        missing_libs.append("requests")

    if missing_libs:
        libs_str = ", ".join(missing_libs)
        error_msg = f"!! FATAL ERROR: Missing library(ies): {libs_str}\n"
        error_msg += f"   Install using: pip install {' '.join(missing_libs)}"
        print(error_msg)
        try:
            import tkinter as tk
            from tkinter import messagebox

            root_err = tk.Tk();
            root_err.withdraw()
            messagebox.showerror("Missing Libraries", error_msg.replace("!! FATAL ERROR: ", ""))
            root_err.destroy()
        except ImportError:
            print("(Could not show graphical error: tkinter missing?)")
        sys.exit(1)

    print("## Initializing JIRA Focus ##")
    app_instance = None
    try:
        app_instance = GUI()
    except Exception as e:
        print(f"!! CRITICAL ERROR during application initialization:")
        traceback.print_exc()
        try:
            import tkinter as tk
            from tkinter import messagebox

            root_err = tk.Tk();
            root_err.withdraw()
            messagebox.showerror("Critical Init Error",
                                 f"Could not initialize:\n\n{type(e).__name__}: {e}\n\nCheck console for details.")
            root_err.destroy()
        except Exception as msg_e:
            print(f"(Could not display init error window: {msg_e})")
        sys.exit(1)