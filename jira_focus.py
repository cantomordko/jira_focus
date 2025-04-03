import json
import os
import re
import sys
import time
import traceback
from collections import Counter

import customtkinter as ctk


class LabelEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent_gui):
        super().__init__(parent_gui.root)
        self.parent_gui = parent_gui
        self.transient(parent_gui.root)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.attributes('-alpha', 0.95)

        self.initial_labels_for_existing_task = set()
        self.current_selection_vars = {}
        self.project_available_labels = []

        if not self.parent_gui.selected_project_key:
            if self.parent_gui.root and self.parent_gui.root.winfo_exists():
                messagebox.showerror("Błąd", "Najpierw wybierz projekt w oknie głównym.", parent=self)
            else:
                print("Błąd: Próba otwarcia edytora etykiet bez wybranego projektu (okno główne nie istnieje?).")
            self.destroy()
            return

        if self.parent_gui.current_jira_issue_key:
            self.title(f"Etykiety dla: {self.parent_gui.current_jira_issue_key}")
        else:
            self.title(f"Etykiety dla nowego zadania (Projekt: {self.parent_gui.selected_project_key})")
        self.geometry("400x450")

        try:
            if self.parent_gui.root and self.parent_gui.root.winfo_exists():
                main_x, main_y = self.parent_gui.root.winfo_x(), self.parent_gui.root.winfo_y()
                main_w, main_h = self.parent_gui.root.winfo_width(), self.parent_gui.root.winfo_height()
                win_w, win_h = 400, 450
                self.geometry(
                    f"{win_w}x{win_h}+{main_x + (main_w // 2) - (win_w // 2)}+{main_y + (main_h // 2) - (win_h // 2)}")
            else:
                self.geometry(f"400x450")
        except Exception as e:
            print(f"Nie można wycentrować okna edytora etykiet: {e}")

        if self.parent_gui.current_jira_issue_key:
            info_text = f"Edytujesz etykiety dla zadania: {self.parent_gui.current_jira_issue_key}"
        else:
            info_text = f"Wybierz etykiety dla nowego zadania w projekcie: {self.parent_gui.selected_project_key}"
        self.info_label = ctk.CTkLabel(self, text=info_text, font=('Courier New', 12), wraplength=380)
        self.info_label.pack(pady=(10, 5), padx=10)

        self.labels_scroll_frame = ctk.CTkScrollableFrame(self, height=250)
        self.labels_scroll_frame.pack(fill='x', padx=10, pady=(0, 5))
        self.labels_scroll_frame.grid_columnconfigure(0, weight=1)

        self.add_label_frame = ctk.CTkFrame(self)
        self.add_label_frame.pack(fill='x', padx=10, pady=(5, 10))

        self.new_label_entry = ctk.CTkEntry(self.add_label_frame, placeholder_text="Dodaj nową etykietę...",
                                            font=('Courier New', 11))
        self.new_label_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.new_label_entry.bind("<Return>", self._add_new_label_from_entry)

        self.add_label_button = ctk.CTkButton(self.add_label_frame, text="Dodaj", font=('Courier New', 11, 'bold'),
                                              width=60, command=self._add_new_label_from_entry)
        self.add_label_button.pack(side='left')

        self.action_button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_button_frame.pack(fill='x', padx=10, pady=(5, 10))
        self.action_button_frame.grid_columnconfigure((0, 1), weight=1)

        if self.parent_gui.current_jira_issue_key:
            self.update_button = ctk.CTkButton(self.action_button_frame, text="Aktualizuj w Jira",
                                               font=('Courier New', 12, 'bold'), command=self._update_jira_labels,
                                               fg_color="green")
            self.update_button.grid(row=0, column=0, padx=(0, 5), sticky='ew')
        else:
            self.save_button = ctk.CTkButton(self.action_button_frame, text="Zapisz dla nowego zadania",
                                             font=('Courier New', 12, 'bold'),
                                             command=self._save_labels_for_new_task_and_close)
            self.save_button.grid(row=0, column=0, padx=(0, 5), sticky='ew')

        self.cancel_button = ctk.CTkButton(self.action_button_frame, text="Anuluj", font=('Courier New', 12, 'bold'),
                                           command=self.destroy, fg_color="gray")
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), sticky='ew')

        self._load_data_and_populate()

    def _load_data_and_populate(self):
        loading_label = ctk.CTkLabel(self.labels_scroll_frame, text="Ładowanie etykiet...", font=('Courier New', 10))
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

            if loading_label and loading_label.winfo_exists():
                loading_label.destroy()
            for widget in self.labels_scroll_frame.winfo_children():
                if widget and widget.winfo_exists():
                    widget.destroy()
            self.current_selection_vars = {}

            if not sorted_labels_to_display:
                ctk.CTkLabel(self.labels_scroll_frame, text="Brak etykiet.", font=('Courier New', 10),
                             text_color="gray").pack(pady=5)
            else:
                for label_name in sorted_labels_to_display:
                    var = ctk.StringVar(value="off")
                    if self.parent_gui.current_jira_issue_key:
                        if label_name in task_labels:
                            var.set("on")
                    elif label_name in self.parent_gui.selected_labels:
                        var.set("on")

                    cb = ctk.CTkCheckBox(
                        self.labels_scroll_frame,
                        text=label_name,
                        variable=var,
                        onvalue="on", offvalue="off",
                        font=('Courier New', 11)
                    )
                    cb.pack(anchor='w', padx=5, pady=1)
                    self.current_selection_vars[label_name] = var

        except Exception as e:
            print(f"[Editor] Błąd podczas ładowania i wypełniania etykiet: {e}")
            traceback.print_exc()
            if loading_label and loading_label.winfo_exists():
                loading_label.destroy()
            try:
                for widget in self.labels_scroll_frame.winfo_children():
                    if widget and widget.winfo_exists():
                        widget.destroy()
                ctk.CTkLabel(self.labels_scroll_frame, text=f"Błąd ładowania:\n{e}", font=('Courier New', 10),
                             text_color="red", wraplength=350).pack(pady=10)
            except Exception as e_disp:
                print(f"Nie można wyświetlić błędu w oknie edytora: {e_disp}")

    def _fetch_project_labels(self):
        if not self.parent_gui.selected_project_key: return []
        print(f"[Editor] Pobieranie etykiet dla projektu {self.parent_gui.selected_project_key}...")
        jql = f'project = "{self.parent_gui.selected_project_key}" ORDER BY updated DESC'
        fields = "labels"
        max_results = 200
        endpoint = f"search?jql={requests.utils.quote(jql)}&fields={fields}&maxResults={max_results}"
        result = self.parent_gui._make_jira_request("GET", endpoint)

        project_labels = []
        if result and result['success'] and 'data' in result and 'issues' in result['data']:
            issues = result['data']['issues']
            all_labels_list = [label for issue in issues if issue.get('fields', {}).get('labels')
                               for label in issue.get('fields', {}).get('labels', [])]
            label_counts = Counter(all_labels_list)
            project_labels = sorted(label_counts.keys(), key=lambda x: (-label_counts[x], x))
            print(f"[Editor] Znaleziono {len(project_labels)} unikalnych etykiet projektu.")
        else:
            print(
                f"[Editor] Nie udało się pobrać etykiet projektu {self.parent_gui.selected_project_key}. Przyczyna: {result.get('error', 'brak danych?')}")
        return project_labels

    def _fetch_current_task_labels(self):
        if not self.parent_gui.current_jira_issue_key:
            return set()

        print(f"[Editor] Pobieranie etykiet dla zadania {self.parent_gui.current_jira_issue_key}...")
        endpoint = f"issue/{self.parent_gui.current_jira_issue_key}?fields=labels"
        result = self.parent_gui._make_jira_request("GET", endpoint)

        task_labels = set()
        if result and result['success'] and 'data' in result:
            task_labels = set(result['data'].get('fields', {}).get('labels', []))
            print(f"[Editor] Znaleziono etykiety dla zadania {self.parent_gui.current_jira_issue_key}: {task_labels}")
        else:
            print(f"[Editor] Nie udało się pobrać etykiet dla zadania {self.parent_gui.current_jira_issue_key}.")
            error_msg = f"Nie można pobrać etykiet dla {self.parent_gui.current_jira_issue_key}."
            if result and not result['success']: error_msg += f"\nBłąd API: {result.get('error', 'Brak')[:100]}..."
            if self.winfo_exists():
                messagebox.showerror("Błąd Pobierania Etykiet", error_msg, parent=self)
        return task_labels

    def _add_new_label_from_entry(self, event=None):
        new_label = self.new_label_entry.get().strip()

        if not new_label:
            print("[Editor] Pole nowej etykiety jest puste.")
            return

        if re.search(r"\s", new_label):
            if self.winfo_exists():
                messagebox.showwarning("Nieprawidłowa Etykieta", f"Etykieta '{new_label}' zawiera spacje.", parent=self)
            return

        if new_label in self.current_selection_vars:
            print(f"[Editor] Etykieta '{new_label}' już istnieje na liście. Zaznaczanie...")
            if new_label in self.current_selection_vars and self.current_selection_vars[new_label]:
                try:
                    self.current_selection_vars[new_label].set("on")
                except Exception as e_set:
                    print(f"Nie można ustawić zmiennej dla {new_label}: {e_set}")
            if self.new_label_entry.winfo_exists():
                self.new_label_entry.delete(0, "end")
            return

        print(f"[Editor] Dodawanie nowej etykiety do UI: {new_label}")
        var = ctk.StringVar(value="on")
        cb = ctk.CTkCheckBox(
            self.labels_scroll_frame,
            text=new_label,
            variable=var,
            onvalue="on", offvalue="off",
            font=('Courier New', 11),
            fg_color="cyan"
        )
        try:
            children = self.labels_scroll_frame.winfo_children()
            first_widget = children[0] if children and children[0].winfo_exists() else None
            cb.pack(anchor='w', padx=5, pady=1, before=first_widget)
            self.current_selection_vars[new_label] = var
            if self.new_label_entry.winfo_exists():
                self.new_label_entry.delete(0, "end")
        except Exception as e_pack:
            print(f"Błąd podczas dodawania checkboxa '{new_label}': {e_pack}")
            if cb and cb.winfo_exists():
                cb.destroy()

    def _get_selected_labels_from_ui(self):
        selected = set()
        for label_name, var in self.current_selection_vars.items():
            if var:
                try:
                    if var.get() == "on":
                        selected.add(label_name)
                except Exception as e_get:
                    print(f"Błąd odczytu zmiennej dla etykiety '{label_name}': {e_get}")
        return selected

    def _update_jira_labels(self):
        if not self.parent_gui.current_jira_issue_key:
            print("[Editor] Błąd: Próba aktualizacji etykiet bez wybranego zadania.")
            if self.winfo_exists(): self.destroy()
            return

        current_selection = self._get_selected_labels_from_ui()
        print(f"[Editor] Aktualizacja etykiet dla {self.parent_gui.current_jira_issue_key} do: {current_selection}")

        if current_selection == self.initial_labels_for_existing_task:
            print("[Editor] Brak zmian w etykietach. Nie wysyłano żądania.")
            if self.winfo_exists():
                messagebox.showinfo("Informacja", "Nie wykryto zmian w etykietach.", parent=self)
                self.destroy()
            return

        valid_labels_list = sorted([lbl for lbl in current_selection if lbl and not re.search(r"\s", lbl)])

        update_data = {
            "fields": {
                "labels": valid_labels_list
            }
        }
        print(f"[Editor] Wysyłanie danych aktualizacji etykiet: {json.dumps(update_data)}")
        endpoint = f"issue/{self.parent_gui.current_jira_issue_key}"
        result = self.parent_gui._make_jira_request("PUT", endpoint, data=json.dumps(update_data))

        if result and result['success'] and result.get('status_code') in [200, 204]:
            print(f"[Editor] Pomyślnie zaktualizowano etykiety dla {self.parent_gui.current_jira_issue_key}.")
            if self.winfo_exists():
                messagebox.showinfo("Sukces",
                                    f"Etykiety dla zadania {self.parent_gui.current_jira_issue_key} zostały zaktualizowane.",
                                    parent=self)
                self.destroy()
        else:
            print(f"[Editor] Nie udało się zaktualizować etykiet dla {self.parent_gui.current_jira_issue_key}.")
            error_msg = f"Nie udało się zaktualizować etykiet dla {self.parent_gui.current_jira_issue_key}."
            if result and result.get('error'):
                error_msg += f"\nBłąd API: {result['error']}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', [])
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nSzczegóły: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result and result.get('raw_response'):
                error_msg += f"\nOdpowiedź serwera (kod {result.get('status_code')}): {result['raw_response'][:200]}..."
            if self.winfo_exists():
                messagebox.showerror("Błąd Aktualizacji Etykiet", error_msg, parent=self)

    def _save_labels_for_new_task_and_close(self):
        try:
            if not self.parent_gui.current_jira_issue_key:
                current_selection = self._get_selected_labels_from_ui()
                print(f"[Editor] Zapisywanie wybranych etykiet dla nowego zadania: {current_selection}")
                self.parent_gui.selected_labels = current_selection
                if hasattr(self.parent_gui, 'edit_labels_button') and self.parent_gui.edit_labels_button.winfo_exists():
                    if current_selection:
                        self.parent_gui.edit_labels_button.configure(text=f"Etykiety ({len(current_selection)})")
                    else:
                        self.parent_gui.edit_labels_button.configure(text="Edytuj Etykiety")
            else:
                print("[Editor] Zamykanie okna edycji dla istniejącego zadania (bez zapisu do selected_labels).")
        except Exception as e:
            print(f"[Editor] Błąd podczas zapisywania etykiet: {e}")
            traceback.print_exc()
        finally:
            if self.winfo_exists():
                self.destroy()

    def _on_closing(self):
        print("[Editor] Okno edytora etykiet zamknięte przez użytkownika.")
        self._save_labels_for_new_task_and_close()


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
        self.selected_project_key = None
        self.current_task_name = ""
        self.current_jira_issue_key = None
        self.start_time = 0
        self.elapsed_time = 0
        self.timer_running = False
        self.selected_labels = set()
        self.my_account_id = None

        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        config = None
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"Załadowano konfigurację z {config_path}")
        except FileNotFoundError:
            print(f"BŁĄD: Nie znaleziono pliku konfiguracyjnego: {config_path}")
            messagebox.showerror("Błąd Konfiguracji", f"Nie znaleziono pliku konfiguracyjnego:\n{config_path}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"BŁĄD: Nieprawidłowy format pliku konfiguracyjnego JSON: {config_path}")
            messagebox.showerror("Błąd Konfiguracji", f"Nieprawidłowy format JSON w pliku:\n{config_path}")
            sys.exit(1)
        except Exception as e:
            print(f"BŁĄD: Nieoczekiwany błąd podczas ładowania konfiguracji z {config_path}: {e}")
            traceback.print_exc()
            messagebox.showerror("Błąd Konfiguracji",
                                 f"Wystąpił nieoczekiwany błąd podczas ładowania konfiguracji:\n{e}")
            sys.exit(1)

        try:
            self.jira_server = config['jira_server'].rstrip('/')
            self.jira_username = config['jira_username']
            self.jira_api_token = config['jira_api_token']
            if not all([self.jira_server, self.jira_username, self.jira_api_token]):
                raise ValueError("Jedna lub więcej wartości w pliku konfiguracyjnym jest pusta.")
        except KeyError as e:
            missing_key = str(e).strip("'")
            print(f"BŁĄD: Brakujący klucz '{missing_key}' w pliku konfiguracyjnym: {config_path}")
            messagebox.showerror("Błąd Konfiguracji",
                                 f"Brakujący klucz '{missing_key}' w pliku konfiguracyjnym:\n{config_path}")
            sys.exit(1)
        except ValueError as e:
            print(f"BŁĄD: {e} w pliku {config_path}")
            messagebox.showerror("Błąd Konfiguracji", f"{e}\n\nSprawdź plik: {config_path}")
            sys.exit(1)
        except Exception as e:
            print(f"BŁĄD: Nieoczekiwany błąd podczas przetwarzania konfiguracji: {e}")
            traceback.print_exc()
            messagebox.showerror("Błąd Konfiguracji",
                                 f"Wystąpił nieoczekiwany błąd podczas przetwarzania konfiguracji:\n{e}")
            sys.exit(1)

        self.auth = (self.jira_username, self.jira_api_token)
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}

        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.geometry("400x500")
        self.root.title("JIRA Focus")
        self.root.resizable(False, False)
        self.root.attributes('-alpha', 0.95)

        self.root.bind("<Control-q>", self.minimize_window)
        self.root.bind("<Control-Shift-q>", self.restore_window)

        self.label = ctk.CTkLabel(self.root, text="JIRA Focus", font=('Courier New', 22))
        self.label.pack(padx=10, pady=(10, 5))

        self.project_label = ctk.CTkLabel(self.root, text="Projekt:", font=('Courier New', 16))
        self.project_label.pack()
        self.project_frame = ctk.CTkFrame(self.root)
        self.project_frame.pack(fill='x', padx=10, pady=(0, 5))
        self.project_combobox = ctk.CTkComboBox(
            self.project_frame, values=self.projects, font=('Courier New', 12),
            dropdown_font=('Courier New', 12), command=self.on_project_select
        )
        self.project_combobox.pack(side='left', fill='x', expand=True)
        self.project_combobox.set("Wybierz projekt")
        self.project_combobox.bind("<KeyPress>", self.prevent_backspace)

        self.category_label = ctk.CTkLabel(self.root, text="Typ zadania:", font=('Courier New', 16))
        self.category_label.pack()
        self.category_frame = ctk.CTkFrame(self.root)
        self.category_frame.pack(fill='x', padx=10, pady=(0, 5))
        self.category_combobox = ctk.CTkComboBox(
            self.category_frame, values=self.categories, font=('Courier New', 12),
            dropdown_font=('Courier New', 12)
        )
        self.category_combobox.pack(side='left', fill='x', expand=True, padx=0)
        self.category_combobox.set("Wybierz typ zadania")
        self.category_combobox.bind("<KeyPress>", self.prevent_backspace)

        self.task_label = ctk.CTkLabel(self.root, text="Nazwa zadania:", font=('Courier New', 16))
        self.task_label.pack()
        self.task_entry = ctk.CTkEntry(self.root, font=('Courier New', 12))
        self.task_entry.pack(fill='x', padx=10, pady=(0, 10))

        self.action_buttons_frame = ctk.CTkFrame(self.root)
        self.action_buttons_frame.pack(fill='x', padx=10, pady=5)
        self.action_buttons_frame.grid_columnconfigure((0, 1), weight=1)

        self.edit_labels_button = ctk.CTkButton(
            self.action_buttons_frame, text="Edytuj Etykiety", font=('Courier New', 12, 'bold'),
            command=self.open_label_editor_window
        )
        self.edit_labels_button.grid(row=0, column=0, padx=(0, 5), sticky='ew')

        self.assign_me_button = ctk.CTkButton(
            self.action_buttons_frame, text="Przypisz do mnie", font=('Courier New', 12, 'bold'),
            command=self.assign_to_me, state='disabled',
            fg_color="#5555CC", hover_color="#4444AA"
        )
        self.assign_me_button.grid(row=0, column=1, padx=(5, 0), sticky='ew')

        self.list_button_frame = ctk.CTkFrame(self.root)
        self.list_button_frame.pack(fill='x', padx=10, pady=5)
        self.history_button = ctk.CTkButton(
            self.list_button_frame, text="Taski w projekcie", font=('Courier New', 12, 'bold'),
            command=self.show_task_list
        )
        self.history_button.pack(fill='x', expand=True, padx=0, pady=0)

        self.timer_buttonframe = ctk.CTkFrame(self.root)
        self.timer_buttonframe.pack(fill='x', padx=10, pady=5)
        self.timer_buttonframe.grid_columnconfigure((0, 1), weight=1)

        self.bstart = ctk.CTkButton(
            self.timer_buttonframe, text='START', font=('Courier New', 12, 'bold'),
            command=self.start_timer, fg_color="green"
        )
        self.bstart.grid(row=0, column=0, padx=(0, 5), pady=0, sticky='ew')

        self.bstop = ctk.CTkButton(
            self.timer_buttonframe, text='STOP', font=('Courier New', 12, 'bold'),
            command=self.stop_timer, state='disabled', fg_color="red"
        )
        self.bstop.grid(row=0, column=1, padx=(5, 0), pady=0, sticky='ew')

        self.timer_label = ctk.CTkLabel(self.root, text="Czas: 00:00:00", font=('Courier New', 16))
        self.timer_label.pack(pady=5)

        self.status_label = ctk.CTkLabel(self.root, text="Zmień status taska:", font=('Courier New', 16))
        self.status_label.pack(pady=(10, 0))
        self.status_buttonframe = ctk.CTkFrame(self.root)
        self.status_buttonframe.pack(fill='x', padx=10, pady=5)
        self.status_buttonframe.grid_columnconfigure((0, 1, 2), weight=1)

        self.bstatus_todo = ctk.CTkButton(
            self.status_buttonframe, text='To Do', font=('Courier New', 12, 'bold'),
            command=lambda: self.change_status_to("To Do"), state='disabled',
            fg_color="#3B8ED0", hover_color="#2F71A8"
        )
        self.bstatus_todo.grid(row=0, column=0, padx=(0, 5), pady=0, sticky='ew')

        self.bstatus_inprogress = ctk.CTkButton(
            self.status_buttonframe, text='In Progress', font=('Courier New', 12, 'bold'),
            command=lambda: self.change_status_to("In Progress"), state='disabled',
            fg_color="#F5A623", hover_color="#C4851C"
        )
        self.bstatus_inprogress.grid(row=0, column=1, padx=(5, 5), pady=0, sticky='ew')

        self.bstatus_done = ctk.CTkButton(
            self.status_buttonframe, text='Done', font=('Courier New', 12, 'bold'),
            command=lambda: self.change_status_to("Done"), state='disabled',
            fg_color="#4CAF50", hover_color="#3A8C40"
        )
        self.bstatus_done.grid(row=0, column=2, padx=(5, 0), pady=0, sticky='ew')

        self._fetch_my_account_id()
        self.load_projects_from_jira()
        if not self.projects:
            self._update_action_button_states()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def prevent_backspace(self, event):
        if event.keysym == "BackSpace":
            return "break"
        return None

    def minimize_window(self, event=None):
        if self.root and self.root.winfo_exists():
            self.root.iconify()
            print("Okno zminimalizowane (Ctrl+Q)")

    def restore_window(self, event=None):
        if self.root and self.root.winfo_exists():
            self.root.deiconify()
            print("Okno przywrócone (Ctrl+Shift+Q)")

    def on_closing(self):
        print("Zamykanie aplikacji JIRA Focus...")
        if self.timer_running:
            print("Ostrzeżenie: Timer był uruchomiony podczas zamykania! Czas nie został zalogowany.")
            self.timer_running = False

        if self.root and self.root.winfo_exists():
            self.root.destroy()
        print("Okno aplikacji zamknięte.")

    def _make_jira_request(self, method, endpoint, **kwargs):
        if not self.jira_server:
            print("BŁĄD: Adres serwera Jira nie jest skonfigurowany.")
            return {'success': False, 'error': 'Adres serwera Jira nie jest skonfigurowany.', 'status_code': None}

        url = f"{self.jira_server}/rest/api/3/{endpoint}"
        log_url = url.split('?')[0]

        log_data_summary = ""
        if 'data' in kwargs and method in ["POST", "PUT"]:
            try:
                data_dict = json.loads(kwargs['data'])
                if isinstance(data_dict.get('fields'), dict):
                    log_data_summary = f" with keys: {list(data_dict.get('fields', {}).keys())}"
                elif isinstance(data_dict.get('transition'), dict):
                    log_data_summary = f" with transition ID: {data_dict['transition'].get('id')}"
                elif 'comment' in data_dict or 'timeSpent' in data_dict:
                    log_data_summary = " with worklog data"
                else:
                    log_data_summary = " with misc data"
            except Exception:
                log_data_summary = " with data (non-JSON?)"

        print(f"-> JIRA API: {method} {log_url}{log_data_summary} ...")

        try:
            response = requests.request(
                method,
                url,
                auth=self.auth,
                headers=self.headers,
                timeout=30,
                **kwargs
            )
            response.raise_for_status()

            if response.status_code == 204:
                print(f"<- JIRA API: {response.status_code} No Content")
                return {'success': True, 'status_code': response.status_code}
            else:
                try:
                    data = response.json()
                    return {'success': True, 'status_code': response.status_code, 'data': data}
                except json.JSONDecodeError:
                    print(
                        f"   Warning: Response from {method} {log_url} was not JSON (status: {response.status_code}). Response text: {response.text[:100]}...")
                    is_success = 200 <= response.status_code < 300
                    return {'success': is_success, 'status_code': response.status_code, 'raw_response': response.text}

        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code if http_err.response else 'N/A'
            response_text = http_err.response.text if http_err.response else 'Brak odpowiedzi'
            error_message = f"Błąd HTTP {status_code} API Jira ({method} {log_url}): {http_err}"
            error_message += f"\nOdpowiedź: {response_text[:500]}..."

            jira_error_details = ""
            try:
                error_json = http_err.response.json()
                jira_error_messages = error_json.get('errorMessages', [])
                jira_errors = error_json.get('errors', {})
                if jira_error_messages: jira_error_details += f"\nKomunikaty Jira: {jira_error_messages}"
                if jira_errors: jira_error_details += f"\nSzczegóły Jira: {jira_errors}"
                error_message += jira_error_details
            except (json.JSONDecodeError, AttributeError):
                pass
            print(f"[API ERROR] {error_message}")
            return {'success': False, 'error': error_message, 'status_code': status_code, 'raw_response': response_text}

        except requests.exceptions.ConnectionError as conn_err:
            err_msg = f"Błąd połączenia API Jira ({method} {log_url}): {conn_err}"
            print(f"[API ERROR] {err_msg}")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd połączenia",
                                     "Nie można połączyć się z serwerem Jira.\nSprawdź adres serwera i połączenie internetowe.",
                                     parent=self.root)
            return {'success': False, 'error': err_msg, 'status_code': None}

        except requests.exceptions.Timeout as timeout_err:
            err_msg = f"Timeout API Jira ({method} {log_url}): {timeout_err}"
            print(f"[API ERROR] {err_msg}")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Timeout", "Zapytanie do Jira przekroczyło limit czasu.", parent=self.root)
            return {'success': False, 'error': err_msg, 'status_code': None}

        except requests.exceptions.RequestException as req_err:
            err_msg = f"Inny błąd zapytania API Jira ({method} {log_url}): {req_err}"
            print(f"[API ERROR] {err_msg}")
            traceback.print_exc()
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd zapytania", f"Wystąpił nieoczekiwany błąd zapytania: {req_err}",
                                     parent=self.root)
            return {'success': False, 'error': err_msg, 'status_code': None}

    def _format_seconds_to_jira_duration(self, seconds):
        seconds = int(seconds)
        if seconds < 0: seconds = 0
        if seconds < 60: return "1m"

        total_minutes = (seconds + 59) // 60

        h, m = divmod(total_minutes, 60)

        parts = []
        if h > 0: parts.append(f"{h}h")
        if m > 0: parts.append(f"{m}m")

        return " ".join(parts) if parts else "1m"

    def _fetch_my_account_id(self):
        print("Pobieranie informacji o użytkowniku (accountId)...")
        result = self._make_jira_request("GET", "myself")
        if result and result['success'] and 'data' in result and 'accountId' in result['data']:
            self.my_account_id = result['data']['accountId']
            print(f"Pomyślnie pobrano accountId: {self.my_account_id}")
        else:
            self.my_account_id = None
            print("BŁĄD: Nie udało się pobrać accountId użytkownika.")
            error_details = result.get('error', 'Brak szczegółów') if result else 'Brak odpowiedzi'
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showwarning("Błąd Pobierania Danych Użytkownika",
                                       f"Nie udało się pobrać Twojego ID użytkownika z Jira.\n"
                                       f"Funkcja 'Przypisz do mnie' będzie niedostępna.\n\n({error_details[:100]}...)",
                                       parent=self.root)

    def load_projects_from_jira(self):
        print("Pobieranie projektów z Jira...")
        result = self._make_jira_request("GET", "project/search")

        self.projects = []
        self.project_keys = {}

        if result and result['success'] and 'data' in result and 'values' in result['data']:
            all_projects = result['data']['values']
            self.projects = sorted([p['name'] for p in all_projects if 'name' in p and 'key' in p])
            self.project_keys = {p['name']: p['key'] for p in all_projects if 'name' in p and 'key' in p}
            print(f"Załadowano {len(self.projects)} projektów.")
            if not self.projects: print("Nie znaleziono projektów w Jira lub brak dostępu.")
        else:
            print("Nie udało się załadować projektów lub brak projektów.")
            if result and not result['success'] and hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd API Projektów",
                                     f"Nie udało się pobrać listy projektów.\nSzczegóły: {result.get('error', 'Brak dodatkowych informacji.')}",
                                     parent=self.root)

        if hasattr(self, 'project_combobox') and self.project_combobox.winfo_exists():
            self.project_combobox.configure(values=self.projects)
            if not self.projects:
                self.project_combobox.set("Brak projektów/Błąd API")
            else:
                self.project_combobox.set("Wybierz projekt")

        self.selected_project_key = None
        self.categories = []
        if hasattr(self, 'category_combobox') and self.category_combobox.winfo_exists():
            self.category_combobox.configure(values=[])
            self.category_combobox.set("Najpierw wybierz projekt")
        if hasattr(self, 'task_entry') and self.task_entry.winfo_exists():
            self.task_entry.delete(0, "end")
        self.selected_labels = set()
        if hasattr(self, 'edit_labels_button') and self.edit_labels_button.winfo_exists():
            self.edit_labels_button.configure(text="Edytuj Etykiety")
        self.current_jira_issue_key = None
        if hasattr(self, 'root') and self.root.winfo_exists():
            self._update_action_button_states()

    def on_project_select(self, choice):
        if self.timer_running:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showwarning("Timer Aktywny", "Zatrzymaj timer przed zmianą projektu.", parent=self.root)
            current_project_name = next(
                (name for name, key in self.project_keys.items() if key == self.selected_project_key), None)
            if current_project_name and hasattr(self, 'project_combobox') and self.project_combobox.winfo_exists():
                self.project_combobox.set(current_project_name)
            return

        selected_key_candidate = self.project_keys.get(choice)
        if selected_key_candidate != self.selected_project_key:
            self.selected_project_key = selected_key_candidate
            if self.selected_project_key:
                print(f"Wybrano projekt: {choice} (Klucz: {self.selected_project_key})")
                if hasattr(self, 'task_entry') and self.task_entry.winfo_exists():
                    self.task_entry.delete(0, "end")
                self.current_jira_issue_key = None
                self.selected_labels = set()
                if hasattr(self, 'edit_labels_button') and self.edit_labels_button.winfo_exists():
                    self.edit_labels_button.configure(text="Edytuj Etykiety")
                self.load_categories_from_jira()
            else:
                print(f"Wybrano nieprawidłowy projekt lub placeholder: {choice}")
                self.selected_project_key = None
                self.categories = []
                if hasattr(self, 'category_combobox') and self.category_combobox.winfo_exists():
                    self.category_combobox.configure(values=self.categories)
                    self.category_combobox.set("Najpierw wybierz projekt")
                if hasattr(self, 'task_entry') and self.task_entry.winfo_exists():
                    self.task_entry.delete(0, "end")
                self.selected_labels = set()
                if hasattr(self, 'edit_labels_button') and self.edit_labels_button.winfo_exists():
                    self.edit_labels_button.configure(text="Edytuj Etykiety")
                self.current_jira_issue_key = None
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self._update_action_button_states()
        else:
            print(f"Projekt {choice} był już wybrany.")

    def load_categories_from_jira(self):
        self.categories = []
        if hasattr(self, 'category_combobox') and self.category_combobox.winfo_exists():
            self.category_combobox.configure(values=[])
            self.category_combobox.set("Ładowanie typów...")

        if not self.selected_project_key:
            print("Nie wybrano projektu do załadowania typów zadań.")
            if hasattr(self, 'category_combobox') and self.category_combobox.winfo_exists():
                self.category_combobox.set("Najpierw wybierz projekt")
            if hasattr(self, 'root') and self.root.winfo_exists():
                self._update_action_button_states()
            return

        print(f"Pobieranie typów zadań dla projektu: {self.selected_project_key}...")
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
                    print(f"Nie znaleziono standardowych typów zadań dla projektu {self.selected_project_key}.")
                else:
                    print(f"Załadowano typy zadań dla {self.selected_project_key}: {len(loaded_categories)}")
            else:
                print(f"Nie znaleziono metadanych dla projektu {self.selected_project_key} w odpowiedzi API.")
        else:
            print(f"Nie udało się załadować metadanych typów zadań dla projektu {self.selected_project_key}.")
            if result and not result['success'] and hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd API Typów Zadań",
                                     f"Nie udało się pobrać typów zadań dla projektu.\nSzczegóły: {result.get('error', 'Brak dodatkowych informacji.')}",
                                     parent=self.root)

        self.categories = loaded_categories
        if hasattr(self, 'category_combobox') and self.category_combobox.winfo_exists():
            self.category_combobox.configure(values=self.categories)
            if not self.categories:
                self.category_combobox.set("Brak typów/Błąd")
            else:
                self.category_combobox.set(self.categories[0] if self.categories else "Wybierz typ")

        if hasattr(self, 'root') and self.root.winfo_exists():
            self._update_action_button_states()

    def open_label_editor_window(self):
        if self.timer_running:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showwarning("Timer Aktywny", "Zatrzymaj timer przed edycją etykiet.", parent=self.root)
            return
        if not self.selected_project_key:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd", "Najpierw wybierz projekt.", parent=self.root)
            return

        if hasattr(self, 'root') and self.root.winfo_exists():
            editor_window = LabelEditorWindow(self)
            editor_window.focus_force()
        else:
            print("Błąd: Nie można otworzyć edytora etykiet, okno główne nie istnieje.")

    def create_jira_issue(self, task_name, issue_type_name, labels_list=None):
        if not self.selected_project_key:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd", "Nie wybrano projektu.", parent=self.root)
            return None
        if not task_name:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd", "Nazwa zadania nie może być pusta.", parent=self.root)
            return None
        if not issue_type_name or issue_type_name not in self.categories:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd",
                                     f"Wybrany typ zadania '{issue_type_name}' jest nieprawidłowy lub niedostępny dla tego projektu.",
                                     parent=self.root)
            return None

        print(
            f"Próba utworzenia zadania dla projektu: {self.selected_project_key}, Typ: {issue_type_name}, Nazwa: {task_name}")
        if labels_list:
            print(f"   Dodawane etykiety: {labels_list}")
        else:
            print("   Brak wybranych etykiet.")

        summary = task_name
        description_text = f"Task created from JIRA Focus app: {task_name}"
        adf_description = {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description_text}]}]
        }

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
                print(f"   Dodano poprawne etykiety: {valid_labels}")
            else:
                print(
                    "   Ostrzeżenie: Lista etykiet była pusta lub zawierała tylko nieprawidłowe etykiety po walidacji.")

        result = self._make_jira_request("POST", "issue", data=json.dumps(issue_data))

        if result and result['success'] and 'data' in result and 'key' in result['data']:
            issue_key = result['data']['key']
            print(f"Pomyślnie utworzono zadanie w Jira: {issue_key}")
            return issue_key
        else:
            print("Nie udało się utworzyć zadania w Jira.")
            error_msg = "Nie udało się utworzyć zadania w Jira."
            if result and result.get('error'):
                error_msg += f"\nBłąd API: {result['error']}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', [])
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nSzczegóły: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result and result.get('raw_response'):
                error_msg += f"\nOdpowiedź serwera (kod {result.get('status_code')}): {result['raw_response'][:200]}..."
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd Tworzenia Zadania", error_msg, parent=self.root)
            return None

    def log_work_to_jira(self, issue_key, elapsed_seconds):
        if not issue_key:
            print("Nie można zalogować czasu: brak klucza zadania.")
            return False

        print(f"Próba zalogowania czasu pracy dla zadania: {issue_key}")
        jira_duration_string = self._format_seconds_to_jira_duration(elapsed_seconds)

        if not jira_duration_string or jira_duration_string == "0m":
            print(f"Błąd: Czas pracy ({elapsed_seconds}s) jest zbyt krótki (minimum 1m). Nie logowano.")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showwarning("Nie Zalogowano Czasu",
                                       f"Czas pracy ({elapsed_seconds}s) jest zbyt krótki do zarejestrowania w Jira (minimum 1 minuta).",
                                       parent=self.root)
            return True

        print(f"Sformatowany i zaokrąglony czas dla Jira: {jira_duration_string} ({elapsed_seconds} sekund)")

        comment_text = f"Czas pracy ({int(elapsed_seconds)}s -> {jira_duration_string}) zarejestrowany przez JIRA Focus."
        adf_comment = {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment_text}]}]
        }
        worklog_data = {
            "timeSpent": jira_duration_string,
            "comment": adf_comment
        }

        endpoint = f"issue/{issue_key}/worklog"
        result = self._make_jira_request("POST", endpoint, data=json.dumps(worklog_data))

        if result and result['success'] and 'data' in result and 'id' in result['data']:
            print(f"Pomyślnie zalogowano czas ({jira_duration_string}) dla zadania {issue_key}.")
            return True
        else:
            print(f"Nie udało się zapisać czasu pracy w Jira dla zadania {issue_key}.")
            error_msg = f"Nie udało się zapisać czasu pracy dla {issue_key}."
            if result and result.get('error'):
                error_msg += f"\nBłąd API: {result.get('error')}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', [])
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nSzczegóły: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result and result.get('raw_response'):
                error_msg += f"\nOdpowiedź serwera (kod {result.get('status_code')}): {result['raw_response'][:200]}..."
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd Logowania Czasu", error_msg, parent=self.root)
            return False

    def _get_available_transitions(self, issue_key):
        if not issue_key: return None
        print(f"Pobieranie dostępnych przejść dla zadania: {issue_key}")
        endpoint = f"issue/{issue_key}/transitions"
        result = self._make_jira_request("GET", endpoint)
        if result and result['success'] and 'data' in result and 'transitions' in result['data']:
            transitions = result['data']['transitions']
            return transitions
        else:
            print(f"Nie udało się pobrać przejść dla {issue_key} lub brak dostępnych przejść.")
            if result and not result['success']:
                print(f"   Błąd API: {result.get('error', 'Brak szczegółów')}")
            elif result and result['success']:
                print("   Odpowiedź API nie zawierała listy 'transitions'.")
            return None

    def _transition_issue(self, issue_key, target_status_name):
        if not issue_key:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd", "Najpierw wybierz lub utwórz zadanie.", parent=self.root)
            return False

        transitions = self._get_available_transitions(issue_key)
        if transitions is None:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd Pobierania Przejść",
                                     f"Nie udało się pobrać dostępnych statusów dla zadania {issue_key}.\nSprawdź połączenie i uprawnienia.",
                                     parent=self.root)
            return False
        if not transitions:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showwarning("Brak Przejść",
                                       f"Nie znaleziono dostępnych przejść dla zadania {issue_key} z jego obecnego stanu.\nMoże to być stan końcowy lub problem z konfiguracją workflow.",
                                       parent=self.root)
            return False

        target_transition_id = None
        target_status_name_lower = target_status_name.lower()
        found_transition_name = "N/A"
        for transition in transitions:
            if transition.get('to', {}).get('name', '').lower() == target_status_name_lower:
                target_transition_id = transition.get('id')
                found_transition_name = transition.get('name', 'N/A')
                print(
                    f"Znaleziono przejście '{found_transition_name}' (ID: {target_transition_id}) prowadzące do statusu '{target_status_name}'.")
                break

        if not target_transition_id:
            available_target_names = sorted(list(set([t.get('to', {}).get('name', 'N/A') for t in transitions])))
            print(
                f"Nie znaleziono przejścia do statusu '{target_status_name}'. Dostępne cele: {available_target_names}")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd Przejścia",
                                     f"Nie można przejść do statusu '{target_status_name}' z obecnego stanu.\n"
                                     f"Dostępne cele: {', '.join(available_target_names)}", parent=self.root)
            return False

        print(
            f"Wykonywanie przejścia '{found_transition_name}' (ID: {target_transition_id}) dla zadania {issue_key}...")
        endpoint = f"issue/{issue_key}/transitions"
        payload = {"transition": {"id": target_transition_id}}
        result = self._make_jira_request("POST", endpoint, data=json.dumps(payload))

        if result and result['success'] and result.get('status_code') == 204:
            print(f"Pomyślnie zmieniono status zadania {issue_key} (przejście do '{target_status_name}').")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showinfo("Sukces", f"Zmieniono status zadania {issue_key} (-> '{target_status_name}').",
                                    parent=self.root)
            return True
        else:
            print(f"Nie udało się zmienić statusu zadania {issue_key} na '{target_status_name}'.")
            error_msg = f"Wystąpił błąd podczas zmiany statusu {issue_key} na '{target_status_name}'."
            if result and result.get('error'):
                error_msg += f"\nBłąd API: {result['error']}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', [])
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nSzczegóły: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result:
                error_msg += f"\nNieoczekiwana odpowiedź serwera (kod {result.get('status_code', 'N/A')}). Sprawdź logi Jira."
            if result and result.get(
                'raw_response'): error_msg += f"\nOdpowiedź: {result.get('raw_response', '')[:200]}..."
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd Przejścia", error_msg, parent=self.root)
            return False

    def change_status_to(self, target_status_name):
        print(f"--- Żądanie zmiany statusu na: {target_status_name} ---")
        if not self.current_jira_issue_key:
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showwarning("Brak zadania",
                                       "Najpierw wybierz zadanie z listy lub rozpocznij pracę nad nowym.",
                                       parent=self.root)
            return
        self._transition_issue(self.current_jira_issue_key, target_status_name)

    def _update_action_button_states(self):
        task_action_state = 'disabled'
        label_edit_state = 'disabled'
        assign_me_state = 'disabled'
        history_button_state = 'disabled'
        start_button_state = 'disabled'
        stop_button_state = 'disabled'

        project_selected = bool(self.selected_project_key)
        task_selected = bool(self.current_jira_issue_key)
        can_interact_with_task = task_selected and not self.timer_running
        can_start_timer = project_selected and not self.timer_running

        if can_interact_with_task:
            task_action_state = 'normal'
        if project_selected and not self.timer_running:
            label_edit_state = 'normal'
            history_button_state = 'normal'
        if can_interact_with_task and self.my_account_id:
            assign_me_state = 'normal'
        if can_start_timer:
            start_button_state = 'normal'
        if self.timer_running:
            stop_button_state = 'normal'
            start_button_state = 'disabled'

        if hasattr(self, 'bstatus_todo') and self.bstatus_todo.winfo_exists(): self.bstatus_todo.configure(
            state=task_action_state)
        if hasattr(self,
                   'bstatus_inprogress') and self.bstatus_inprogress.winfo_exists(): self.bstatus_inprogress.configure(
            state=task_action_state)
        if hasattr(self, 'bstatus_done') and self.bstatus_done.winfo_exists(): self.bstatus_done.configure(
            state=task_action_state)
        if hasattr(self,
                   'edit_labels_button') and self.edit_labels_button.winfo_exists(): self.edit_labels_button.configure(
            state=label_edit_state)
        if hasattr(self, 'assign_me_button') and self.assign_me_button.winfo_exists(): self.assign_me_button.configure(
            state=assign_me_state)
        if hasattr(self, 'history_button') and self.history_button.winfo_exists(): self.history_button.configure(
            state=history_button_state)
        if hasattr(self, 'bstart') and self.bstart.winfo_exists(): self.bstart.configure(state=start_button_state)
        if hasattr(self, 'bstop') and self.bstop.winfo_exists(): self.bstop.configure(state=stop_button_state)

    def assign_to_me(self):
        print("--- Żądanie przypisania zadania do mnie ---")

        if self.timer_running:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showwarning("Timer Aktywny",
                                                                                          "Zatrzymaj timer przed przypisaniem zadania.",
                                                                                          parent=self.root)
            return
        if not self.current_jira_issue_key:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("Brak zadania",
                                                                                        "Najpierw wybierz zadanie z listy.",
                                                                                        parent=self.root)
            return
        if not self.my_account_id:
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("Błąd Konfiguracji",
                                                                                        "Nie udało się pobrać Twojego ID użytkownika z Jira.\nFunkcja niedostępna.",
                                                                                        parent=self.root)
            return

        print(
            f"Próba przypisania zadania {self.current_jira_issue_key} do użytkownika z accountId: {self.my_account_id}")

        payload = {
            "fields": {
                "assignee": {"accountId": self.my_account_id}
            }
        }
        endpoint = f"issue/{self.current_jira_issue_key}/assignee"
        assignee_payload = {"accountId": self.my_account_id}

        result = self._make_jira_request("PUT", endpoint, data=json.dumps(assignee_payload))

        if result and result['success'] and result.get('status_code') in [200, 204]:
            print(f"Pomyślnie przypisano zadanie {self.current_jira_issue_key} do Ciebie.")
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showinfo("Sukces",
                                                                                       f"Zadanie {self.current_jira_issue_key} zostało przypisane do Ciebie.",
                                                                                       parent=self.root)
        else:
            print(f"Nie udało się przypisać zadania {self.current_jira_issue_key}.")
            error_msg = f"Wystąpił błąd podczas przypisywania zadania {self.current_jira_issue_key}."
            if result and result.get('error'):
                error_msg += f"\nBłąd API: {result.get('error')}"
            elif result and 'data' in result:
                api_errors = result['data'].get('errorMessages', [])
                api_details = result['data'].get('errors', {})
                if api_errors: error_msg += "\n" + "\n".join(api_errors)
                if api_details: error_msg += "\nSzczegóły: " + ", ".join([f"{k}: {v}" for k, v in api_details.items()])
            elif result and result.get('raw_response'):
                error_msg += f"\nOdpowiedź serwera (kod {result.get('status_code')}): {result['raw_response'][:200]}..."
            if hasattr(self, 'root') and self.root.winfo_exists(): messagebox.showerror("Błąd Przypisywania", error_msg,
                                                                                        parent=self.root)

    def start_timer(self):
        if not hasattr(self, 'root') or not self.root.winfo_exists():
            print("Błąd: Okno główne nie istnieje, nie można uruchomić timera.")
            return
        if self.timer_running:
            print("Timer jest już uruchomiony.");
            return

        self.current_task_name = self.task_entry.get().strip()
        selected_issue_type = self.category_combobox.get()
        selected_project_display_name = self.project_combobox.get()

        if not self.selected_project_key:
            messagebox.showerror("Błąd", "Nie wybrano projektu.", parent=self.root);
            return
        if not selected_issue_type or selected_issue_type not in self.categories:
            messagebox.showerror("Błąd",
                                 f"Wybrany typ zadania '{selected_issue_type}' jest nieprawidłowy lub niedostępny.",
                                 parent=self.root);
            return
        if not self.current_task_name:
            messagebox.showerror("Błąd", "Nazwa zadania nie może być pusta.", parent=self.root);
            return
        if selected_project_display_name not in self.project_keys or self.project_keys[
            selected_project_display_name] != self.selected_project_key:
            messagebox.showerror("Błąd",
                                 f"Wybrany projekt '{selected_project_display_name}' nie jest zgodny lub dostępny. Wybierz ponownie.",
                                 parent=self.root)
            self.load_projects_from_jira();
            return

        issue_key_to_use = self.current_jira_issue_key
        if not issue_key_to_use:
            print("Nie wybrano istniejącego zadania, próba utworzenia nowego...")
            final_labels_list = sorted(list(self.selected_labels))
            print(f"Używane etykiety dla nowego zadania: {final_labels_list}")

            new_issue_key = self.create_jira_issue(self.current_task_name, selected_issue_type, final_labels_list)
            if new_issue_key:
                issue_key_to_use = new_issue_key
                self.current_jira_issue_key = new_issue_key
                print(f"Ustawiono klucz bieżącego zadania na nowo utworzone: {self.current_jira_issue_key}")
                self.selected_labels = set()
                if hasattr(self, 'edit_labels_button') and self.edit_labels_button.winfo_exists():
                    self.edit_labels_button.configure(text="Edytuj Etykiety")
            else:
                print("Timer nie zostanie uruchomiony z powodu błędu tworzenia zadania.")
                return
        else:
            print(f"Używanie istniejącego zadania wybranego z listy: {issue_key_to_use}")

        if issue_key_to_use:
            self.current_jira_issue_key = issue_key_to_use
            self.start_time = time.time()
            self.elapsed_time = 0
            self.timer_running = True
            print(f"Timer uruchomiony dla zadania: {self.current_jira_issue_key} - {self.current_task_name}")
            self.update_timer()

            if hasattr(self, 'bstart'): self.bstart.configure(text='WORKING...')
            if hasattr(self, 'project_combobox'): self.project_combobox.configure(state='disabled')
            if hasattr(self, 'category_combobox'): self.category_combobox.configure(state='disabled')
            if hasattr(self, 'task_entry'): self.task_entry.configure(state='disabled')
            self._update_action_button_states()

        else:
            print("Błąd krytyczny: Brak klucza zadania Jira po próbie utworzenia/wybrania.")
            if hasattr(self, 'root') and self.root.winfo_exists():
                messagebox.showerror("Błąd Wewnętrzny",
                                     "Nie udało się uzyskać klucza zadania Jira do uruchomienia timera.",
                                     parent=self.root)

    def stop_timer(self):
        if not self.timer_running:
            print("Timer nie był uruchomiony.")
            return

        self.timer_running = False
        if self.start_time > 0:
            self.elapsed_time = time.time() - self.start_time
        else:
            self.elapsed_time = 0
            print("Ostrzeżenie: start_time był nieprawidłowy podczas zatrzymywania timera.")

        elapsed_seconds = int(self.elapsed_time)
        print(f"Timer zatrzymany. Całkowity czas pracy: {elapsed_seconds} sekund.")

        log_success = False
        if self.current_jira_issue_key:
            log_success = self.log_work_to_jira(self.current_jira_issue_key, elapsed_seconds)
        else:
            print("Ostrzeżenie: Brak klucza zadania Jira podczas zatrzymywania timera. Nie można zalogować czasu.")
            log_success = True

        last_logged_time_str = self._format_seconds_to_jira_duration(self.elapsed_time)
        if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
            self.timer_label.configure(text=f"Ostatni: {last_logged_time_str} ({elapsed_seconds}s)")

        if hasattr(self, 'bstart') and self.bstart.winfo_exists(): self.bstart.configure(text='START')
        if hasattr(self, 'project_combobox') and self.project_combobox.winfo_exists(): self.project_combobox.configure(
            state='normal')
        if hasattr(self,
                   'category_combobox') and self.category_combobox.winfo_exists(): self.category_combobox.configure(
            state='normal')
        if hasattr(self, 'task_entry') and self.task_entry.winfo_exists(): self.task_entry.configure(state='normal')

        self._update_action_button_states()

        self.start_time = 0

    def update_timer(self):
        if self.timer_running and hasattr(self, 'root') and self.root.winfo_exists():
            if self.start_time > 0:
                current_elapsed = time.time() - self.start_time
                h, rem = divmod(int(current_elapsed), 3600)
                m, s = divmod(rem, 60)
                time_string = f"Czas: {h:02d}:{m:02d}:{s:02d}"
                if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
                    self.timer_label.configure(text=time_string)
                if self.timer_running:
                    self.root.after(1000, self.update_timer)
            else:
                print("Ostrzeżenie: Próba aktualizacji timera bez prawidłowego czasu startu.")
                if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
                    self.timer_label.configure(text="Czas: --:--:--")
        elif not self.timer_running:
            pass
        else:
            print("Zatrzymano pętlę timera, ponieważ okno główne nie istnieje.")
            self.timer_running = False

    def show_task_list(self):
        if not hasattr(self, 'root') or not self.root.winfo_exists():
            print("Błąd: Nie można pokazać listy tasków, okno główne nie istnieje.")
            return

        if self.timer_running:
            messagebox.showinfo("Timer Aktywny", "Zatrzymaj timer przed przeglądaniem tasków.", parent=self.root)
            return
        if not self.selected_project_key:
            messagebox.showerror("Brak Projektu", "Najpierw wybierz projekt, aby zobaczyć taski.", parent=self.root)
            return

        task_window = ctk.CTkToplevel(self.root)
        task_window.title(f"Taski w projekcie: {self.selected_project_key}")
        task_window.geometry("750x500")
        task_window.transient(self.root)
        task_window.grab_set()
        task_window.attributes('-alpha', 0.95)
        try:
            main_x, main_y, main_w, main_h = self.root.winfo_x(), self.root.winfo_y(), self.root.winfo_width(), self.root.winfo_height()
            win_w, win_h = 750, 500
            task_window.geometry(
                f"{win_w}x{win_h}+{main_x + (main_w // 2) - (win_w // 2)}+{main_y + (main_h // 2) - (win_h // 2)}")
        except Exception as e:
            print(f"Nie można wycentrować okna tasków: {e}")

        scrollable_frame = ctk.CTkScrollableFrame(task_window,
                                                  label_text=f"Taski w projekcie: {self.selected_project_key}")
        scrollable_frame.pack(fill='both', padx=10, pady=(5, 0), expand=True)

        loading_label = ctk.CTkLabel(scrollable_frame, text="Pobieranie tasków...", font=('Courier New', 12))
        loading_label.pack(pady=20)
        self.root.update_idletasks()

        print(f"Pobieranie tasków dla projektu {self.selected_project_key}...")
        jql = f'project = "{self.selected_project_key}" ORDER BY updated DESC'
        fields = "summary,status,issuetype,worklog,labels,assignee"
        max_results = 50
        endpoint = f"search?jql={requests.utils.quote(jql)}&fields={fields}&maxResults={max_results}"
        result = self._make_jira_request("GET", endpoint)

        if loading_label.winfo_exists(): loading_label.destroy()
        for widget in scrollable_frame.winfo_children():
            if widget != scrollable_frame._scrollbar:
                widget.destroy()

        if result and result['success'] and 'data' in result and 'issues' in result['data']:
            issues = result['data']['issues']
            total_found = result['data'].get('total', len(issues))
            print(
                f"Znaleziono {len(issues)} tasków (z {total_found} pasujących) dla projektu {self.selected_project_key}.")
            if not issues:
                ctk.CTkLabel(scrollable_frame, text="Brak tasków w tym projekcie.", font=('Courier New', 12)).pack(
                    pady=10)
            else:
                for issue in issues:
                    try:
                        issue_key = issue.get('key', 'NO-KEY')
                        fields_data = issue.get('fields', {})
                        summary = fields_data.get('summary', 'Brak podsumowania')
                        status_name = fields_data.get('status', {}).get('name', 'Nieznany St.')
                        issue_type_name = fields_data.get('issuetype', {}).get('name', 'Nieznany Typ')
                        labels = fields_data.get('labels', [])
                        total_time_seconds = sum(
                            wl.get('timeSpentSeconds', 0) for wl in fields_data.get('worklog', {}).get('worklogs', []))
                        time_str = self._format_seconds_to_jira_duration(
                            total_time_seconds) if total_time_seconds > 0 else "0m"
                        label_str = f" [{', '.join(labels)}]" if labels else ""

                        assignee_data = fields_data.get('assignee')
                        assignee_name = assignee_data.get('displayName',
                                                          'Brak nazwy') if assignee_data else 'Nieprzypisane'

                        display_text = f"[{issue_key}] {summary} ({status_name}) [{assignee_name}]{label_str} - Czas: {time_str}"

                        task_frame = ctk.CTkFrame(scrollable_frame, fg_color="transparent")
                        task_frame.pack(fill='x', pady=2)
                        task_button = ctk.CTkButton(
                            task_frame, text=display_text,
                            font=('Courier New', 12),
                            anchor='w',
                            fg_color="#444444", hover_color="#555555",
                            command=lambda s=summary, k=issue_key, t=issue_type_name, l=labels, a=assignee_data,
                                           win=task_window: self.select_task(s, k, t, l, a, win)
                        )
                        task_button.pack(fill='x', padx=5)
                    except Exception as issue_e:
                        print(f"Błąd przetwarzania taska {issue.get('key', 'N/A')}: {issue_e}")
                        ctk.CTkLabel(scrollable_frame, text=f"Błąd wczytywania taska {issue.get('key', 'N/A')}",
                                     font=('Courier New', 10), text_color="orange").pack(pady=2)

        else:
            print("Błąd podczas pobierania tasków z Jira lub brak wyników.")
            error_text = "Błąd pobierania tasków z Jira lub brak wyników."
            if result and not result['success']:
                error_text += f"\nSzczegóły: {result.get('error', 'Brak')[:200]}..."
            ctk.CTkLabel(scrollable_frame, text=error_text, font=('Courier New', 12), text_color="red",
                         wraplength=700).pack(pady=10)

        button_frame = ctk.CTkFrame(task_window)
        button_frame.pack(fill='x', padx=10, pady=(5, 10))
        refresh_btn = ctk.CTkButton(button_frame, text="Odśwież",
                                    command=lambda win=task_window: self.refresh_task_list_window(win),
                                    font=('Courier New', 12, 'bold'), width=120)
        refresh_btn.pack(side='left', padx=(0, 5))
        close_btn = ctk.CTkButton(button_frame, text="Zamknij", command=task_window.destroy,
                                  font=('Courier New', 12, 'bold'), width=120)
        close_btn.pack(side='right', padx=(5, 0))
        task_window.protocol("WM_DELETE_WINDOW", task_window.destroy)

    def refresh_task_list_window(self, window):
        print("Odświeżanie listy tasków...")
        if window and window.winfo_exists():
            window.destroy()
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(150, self.show_task_list)

    def select_task(self, summary, issue_key, issue_type_name, labels, assignee_data, window):
        if not hasattr(self, 'root') or not self.root.winfo_exists():
            print("Błąd: Okno główne nie istnieje, nie można wybrać taska.")
            if window and window.winfo_exists(): window.destroy()
            return

        if self.timer_running:
            messagebox.showwarning("Timer Aktywny", "Nie można wybrać nowego zadania, gdy timer jest uruchomiony.",
                                   parent=window)
            if window and window.winfo_exists(): window.focus_force()
            return

        assignee_name = assignee_data.get('displayName', 'Nieprzypisane') if assignee_data else 'Nieprzypisane'
        print(
            f"Wybrano zadanie z listy: {summary} (Klucz: {issue_key}, Typ: {issue_type_name}, Etykiety: {labels}, Przypisany: {assignee_name})")

        if hasattr(self, 'task_entry') and self.task_entry.winfo_exists():
            self.task_entry.delete(0, "end")
            self.task_entry.insert(0, summary)

        if hasattr(self, 'category_combobox') and self.category_combobox.winfo_exists():
            if issue_type_name and issue_type_name in self.categories:
                self.category_combobox.set(issue_type_name)
            else:
                print(
                    f"Ostrzeżenie: Typ zadania '{issue_type_name}' nie znaleziony w załadowanych typach dla projektu {self.selected_project_key}. Ustawianie domyślnego.")
                default_type = self.categories[0] if self.categories else "Wybierz typ"
                self.category_combobox.set(default_type)

        self.selected_labels = set()
        if hasattr(self, 'edit_labels_button') and self.edit_labels_button.winfo_exists():
            self.edit_labels_button.configure(text="Edytuj Etykiety")
        print("   Wyczyszczono stan etykiet dla tworzenia nowych zadań.")

        self.current_jira_issue_key = issue_key
        self.current_task_name = summary

        self._update_action_button_states()
        if window and window.winfo_exists():
            window.destroy()


if __name__ == "__main__":
    try:
        import customtkinter
        import requests
    except ImportError as e:
        print(f"BŁĄD: Brak wymaganej biblioteki: {e.name}")
        print("Uruchom: pip install customtkinter requests")
        try:
            import tkinter as tk
            from tkinter import messagebox

            root_err = tk.Tk()
            root_err.withdraw()
            messagebox.showerror("Brak Biblioteki",
                                 f"Brak wymaganej biblioteki: {e.name}\n\nZainstaluj ją używając:\npip install customtkinter requests")
            root_err.destroy()
        except ImportError:
            pass
        sys.exit(1)

    print("Uruchamianie JIRA Focus...")
    app_instance = None
    try:
        app_instance = GUI()
    except Exception as e:
        print(f"Wystąpił krytyczny błąd podczas inicjalizacji aplikacji:")
        traceback.print_exc()
        try:
            import tkinter as tk
            from tkinter import messagebox

            root_err = tk.Tk()
            root_err.withdraw()
            messagebox.showerror("Błąd Krytyczny",
                                 f"Nie można zainicjalizować aplikacji z powodu błędu:\n\n{type(e).__name__}: {e}\n\nSprawdź konsolę.")
            root_err.destroy()
        except Exception as msg_e:
            print(f"Nie można wyświetlić okna błędu inicjalizacji: {msg_e}")
        sys.exit(1)

    print("Aplikacja JIRA Focus zakończyła działanie.")
