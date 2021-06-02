import email
import imaplib
import os
import re
import time
import webbrowser
from email.header import decode_header
from email.message import EmailMessage
from smtplib import SMTP_SSL, SMTP_SSL_PORT

from src.models.Program import Program
from src.models.test_result import TestResult


class EmailReader(object):
    folder = "inbox"

    def __init__(self, email: str, password: str, provider: str, subject_prefix: str, emails_dict: dict, smtp_provider: str):
        self.email = email
        self.password = password
        self.provider = provider
        self.subject_prefix = subject_prefix

        self.smtp_server = SMTP_SSL(smtp_provider, port=SMTP_SSL_PORT)
        self.smtp_server.set_debuglevel(1)  # Show SMTP server interactions
        self.smtp_server.login(email, password)

        self.emails = {}
        for mail, name in emails_dict.items():
            self.emails[mail] = name

    def read_programs(self):

        programs = list()
        mail = imaplib.IMAP4_SSL(self.provider)

        mail.login(self.email, self.password)

        mail.select(self.folder)

        n = 0
        (retcode, messages) = mail.search(None, "(UNSEEN)")
        if retcode == "OK":

            for num in messages[0].split():
                print("Processing ")
                n = n + 1
                typ, data = mail.fetch(num, "(RFC822)")
                for response_part in data:
                    if isinstance(response_part, tuple):
                        # parse a bytes email into a message object
                        msg = email.message_from_bytes(response_part[1])
                        # decode the email subject
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            # if it's a bytes, decode to str
                            subject = subject.decode(encoding)

                        # пропускаем с ненужным сабжектом
                        if re.match(f"{self.subject_prefix}\\d", subject) is None:
                            continue
                        # decode email sender
                        From, encoding = decode_header(msg.get("From"))[1]
                        if isinstance(From, bytes):
                            if encoding is not None:
                                From = From.decode(encoding)
                            else:
                                From = From.decode("utf-8")

                            From = From.replace("<", "")
                            From = From.replace(">", "")
                            From = From.replace(" ", "")

                        if self.emails.get(From) is None:
                            continue

                        print("Subject:", subject)
                        print("From:", From)

                        program_type = self.remove_prefix(subject, self.subject_prefix)

                        if msg.is_multipart():
                            # iterate over email parts
                            for part in msg.walk():
                                # extract content type of email
                                content_type = part.get_content_type()
                                content_disposition = str(
                                    part.get("Content-Disposition")
                                )
                                try:
                                    # get the email body
                                    body = part.get_payload(decode=True).decode()
                                except:
                                    pass
                                if (
                                    content_type == "text/plain"
                                    and "attachment" not in content_disposition
                                ):
                                    # print text/plain emails and skip attachments
                                    print(body)  # TODO: log it
                                elif "attachment" in content_disposition:
                                    # download attachment
                                    filename = part.get_filename()
                                    if filename:
                                        folder_name = clean(subject)
                                        if not os.path.isdir(folder_name):
                                            # make a folder for this email (named after the subject)
                                            os.mkdir(folder_name)
                                        filepath = os.path.join(folder_name, filename)
                                        # download attachment and save it

                                        programs.append(
                                            Program(
                                                program_type,
                                                part.get_payload(decode=True).decode(
                                                    "utf-8"
                                                ),
                                                self.emails.get(From),
                                                time.time(),
                                            )
                                        )
                                        open(filepath, "wb").write(
                                            part.get_payload(decode=True)
                                        )


            programs.sort(key=lambda program: program.date)

            unique = {}
            for program in programs:
                if unique.get(f"{program.owner_email}_{program.type}") is None:
                    unique[f"{program.owner_email}_{program.type}"] = True
                else:
                    programs.remove(program)

            return programs

    def remove_prefix(self, text, prefix):
        if text.startswith(prefix):
            return text[len(prefix) :]
        return text  # or whatever


    def send_failed_test(self, test: TestResult):
        # Craft the email by hand
        from_email = f'<{self.email}>'  # or simply the email address
        to_emails = [test.email]
        email_message = EmailMessage()
        email_message.add_header('To', ', '.join(to_emails))
        email_message.add_header('From', from_email)
        email_message.add_header('Subject', f"{self.subject_prefix}{test.type}")
        email_message.add_header('X-Priority', '1')  # Urgency, 1 highest, 5 lowest
        email_message.set_content(f"{test.email}, задача №{test.type}, тест: [команда: {test.test}, ожидалось: {test.expected}, получено: {test.actual}]")
        self.smtp_server.sendmail(from_email, to_emails, email_message.as_bytes())

    def send_success_email(self, email: str, type: int):
        # Craft the email by hand
        from_email = f'<{self.email}>'  # or simply the email address
        to_emails = [email]
        email_message = EmailMessage()
        email_message.add_header('To', ', '.join(to_emails))
        email_message.add_header('From', from_email)
        email_message.add_header('Subject', f"{self.subject_prefix}{type}")
        email_message.add_header('X-Priority', '1')  # Urgency, 1 highest, 5 lowest
        email_message.set_content(
            f"{email}, задача №{type} принята")
        self.smtp_server.sendmail(from_email, to_emails, email_message.as_bytes())


def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)
