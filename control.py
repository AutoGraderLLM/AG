"""
control code
"""
import os
import sqlite3
import subprocess
import sys
import shutil

def extract_student_id():
        """
        Extract the student's GitHub repository name or directory from the command-line argument.
        If an argument is provided, it is considered as the student's repository name.
        If not, the script will exit with an error message.
        """
        if len(sys.argv) > 1:
                # sys.argv[1] holds the first command-line argument passed to the script
                user_repo = sys.argv[1]
                print(f"Repository or Directory Name: {user_repo}")
                return user_repo
        else:
                # If no argument is given, print error and exit
                print("Error: No repository name provided.")
                sys.exit(1)


def fetch_data_from_directories(student_code_dir, autograder_output_file, readme_file):
        """
        Fetch data from the specified directories and files with proper encoding handling.
        This function attempts to read student code files, autograder output, and professor instructions.

        :param student_code_dir: Directory containing student code files.
        :param autograder_output_file: Path to the autograder output file.
        :param readme_file: Path to the professor instructions (README).
        :return: A tuple containing:
                         - A string with all student code content.
                         - A string with the autograder output.
                         - A string with the professor instructions.
        """
        student_code_data = ""
        # Iterate over each file in the student code directory
        for filename in os.listdir(student_code_dir):
                file_path = os.path.join(student_code_dir, filename)
                if os.path.isfile(file_path):
                        # Try reading the file using UTF-8 encoding first
                        try:
                                with open(file_path, 'r', encoding='utf-8') as file:
                                        student_code_data += f"File: {filename}\n{file.read()}\n\n"
                        except UnicodeDecodeError:
                                # If UTF-8 fails, try ISO-8859-1 encoding
                                try:
                                        with open(file_path, 'r', encoding='ISO-8859-1') as file:
                                                student_code_data += f"File: {filename}\n{file.read()}\n\n"
                                except UnicodeDecodeError:
                                        # If both encodings fail, print a warning and skip the file
                                        print(f"Warning: Could not read file {filename} due to encoding issues.")

        # Read the autograder output with encoding handling
        try:
                with open(autograder_output_file, 'r', encoding='utf-8') as file:
                        autograder_output = file.read()
        except UnicodeDecodeError:
                with open(autograder_output_file, 'r', encoding='ISO-8859-1') as file:
                        autograder_output = file.read()

        # Read the professor instructions with encoding handling
        try:
                with open(readme_file, 'r', encoding='utf-8') as file:
                        professor_instructions = file.read()
        except UnicodeDecodeError:
                with open(readme_file, 'r', encoding='ISO-8859-1') as file:
                        professor_instructions = file.read()

        return student_code_data, autograder_output, professor_instructions

def send_data_to_ollama(student_code_data, autograder_output, professor_instructions):
        """
        Send combined data (student code, autograder output, professor instructions) to the Ollama model.
        
        The Ollama model ux1 is a subprocess call that takes a prompt as input and returns a response.
        If an error occurs, it returns a dictionary containing the error message.
        Otherwise, it returns a dictionary with the response.
        """
        prompt = (
                f"DO NOT CORRECT THE CODE!!! ONLY PROVIDE Question-based guided FEEDBACK BASED ON THIS:\n"
                f"**Student Code:**\n{student_code_data}\n\n"
                f"**Autograder Output:**\n{autograder_output}\n\n"
                f"**Professor Instructions:**\n{professor_instructions}\n\n"
        )

        try:
                # Call the 'ollama ux1' model with the prompt as input
                result = subprocess.run(
                        ['ollama', 'run', 'ux1'],
                        input=prompt,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                )
                # Check the return code to identify any subprocess errors
                if result.returncode != 0:
                        print(f"Error running Ollama: {result.stderr}")
                        return {"error": result.stderr}
                # If successful, return the stdout response
                return {"response": result.stdout}
        except Exception as e:
                # Catch any unexpected exceptions
                print(f"Failed to run Ollama model: {e}")
                return {"error": str(e)}


def write_feedback_to_file(student_id, assignment_id, feedback):
        """
        Write the generated feedback to a Markdown file.
        
        :param student_id: The ID of the student (repository name).
        :param assignment_id: The assignment ID (hard-coded in this script).
        :param feedback: The feedback text generated by the Ollama model.
        :return: The path to the feedback file if successful, otherwise None.
        """
        cwd = os.getcwd()
        feedback_file_path = os.path.join(cwd, 'feedback.md')
        try:
                # Write feedback to the specified markdown file
                with open(feedback_file_path, 'w', encoding='utf-8') as file:
                        file.write(f"# Feedback for {student_id}\n\n")
                        file.write(feedback)
                print(f"Feedback saved to {feedback_file_path}")
                home = os.getenv('HOME') or cwd
                logs_dir = os.path.join(home, 'logs')
                if os.path.isdir(logs_dir):
                        dest = os.path.join(logs_dir, 'feedback.md')
                        try:
                                shutil.copy(feedback_file_path, dest)  # ADDED: copy feedback to logs
                                print(f"Copied feedback to logs directory: {dest}")  # ADDED: confirm copy
                                return dest  # ADDED: return logs path
                        except Exception as copy_err:
                                print(f"Failed to copy feedback to logs: {copy_err}")
                return feedback_file_path
        except Exception as e:
                # If writing to file fails, print error and return None
                print(f"Failed to write to Feedback.md: {e}")
                return None

def insert_into_database(student_id, assignment_id, test_id, feedback, feedback_file_path, student_code_dir, autograder_output_file):
        """
        Insert all retrieved and generated data into the SQLite database.
        
        This includes:
        - Student code into the submissions table
        - Autograder output into the autograder_outputs table
        - Feedback into the feedback table
        
        :param student_id: The student's repository name.
        :param assignment_id: The assignment ID.
        :param test_id: The test ID.
        :param feedback: The feedback text generated.
        :param feedback_file_path: The path to the feedback file.
        :param student_code_dir: Directory containing the student code files.
        :param autograder_output_file: The path to the autograder output file.
        """
        db_path = os.path.join(os.getenv("HOME"), "agllmdatabase.db")
        conn = None

        try:
                # Connect to the SQLite database
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Insert each student code file into the submissions table
                for filename in os.listdir(student_code_dir):
                        file_path = os.path.join(student_code_dir, filename)
                        if os.path.isfile(file_path):
                                # Read the code file content
                                with open(file_path, 'r', encoding='utf-8') as file:
                                        code_content = file.read()
                                cursor.execute(
                                        '''
                                        INSERT INTO submissions (student_repo, assignment_id, code, submitted_at)
                                        VALUES (?, ?, ?, datetime('now', 'utc'))
                                        ''',
                                        (student_id, assignment_id, code_content)
                                )

                # Get the submission ID of the last inserted row to link to feedback and autograder outputs
                submission_id = cursor.lastrowid

                # Insert the autograder output into autograder_outputs table
                with open(autograder_output_file, 'r', encoding='utf-8') as file:
                        autograder_output = file.read()
                cursor.execute(
                        '''
                        INSERT INTO autograder_outputs (submission_id, output, generated_at)
                        VALUES (?, ?, datetime('now', 'utc'))
                        ''',
                        (submission_id, autograder_output)
                )

                # Insert the feedback into the feedback table
                cursor.execute(
                        '''
                        INSERT INTO feedback (submission_id, feedback_text, generated_at)
                        VALUES (?, ?, datetime('now', 'utc'))
                        ''',
                        (submission_id, feedback)
                )

                # Commit all changes to the database
                conn.commit()
                print("Data successfully inserted into the database.")

        except sqlite3.Error as e:
                # Catch and print any SQLite errors
                print(f"SQLite error: {e}")

        finally:
                # Close the database connection
                if conn:
                        conn.close()
def main():
        # Define the paths for directories and files
        student_code_dir = os.path.expanduser('~/logs/studentcode')
        autograder_output_file = os.path.expanduser('~/logs/autograder_output.txt')
        readme_file = os.path.expanduser('~/logs/README.md')

        # Extract the student ID (based on repository name) from command-line arguments
        student_id = extract_student_id()

        # Set assignment_id and test_id (hard-coded values for this example)
        assignment_id = 101
        test_id = 1001

        # Fetch all the necessary data: student code, autograder output, and professor instructions
        student_code_data, autograder_output, professor_instructions = fetch_data_from_directories(
                student_code_dir, autograder_output_file, readme_file
        )

        # Send the combined data to the Ollama model for feedback generation
        model_response = send_data_to_ollama(student_code_data, autograder_output, professor_instructions)

        # If the model responded without error, proceed with writing feedback and database insertion
        if "error" not in model_response:
                feedback = model_response.get("response", "No feedback generated.")
                feedback_file_path = write_feedback_to_file(student_id, assignment_id, feedback)
                # If feedback was successfully written to file, insert data into the database
                if feedback_file_path:
                        insert_into_database(student_id, assignment_id, test_id, feedback, feedback_file_path, student_code_dir, autograder_output_file)
        else:
                # If there was an error in generating feedback, print the error message
                print("Error in generating feedback:", model_response["error"])


if __name__ == "__main__":
        main()
