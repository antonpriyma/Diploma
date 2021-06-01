import email
import imaplib
import os
import re
import time
import webbrowser
from email.header import decode_header

from src.models.Program import Program


class EmailReader(object):
    folder = "inbox"

    def __init__(self, email: str, password: str, provider: str, subject_prefix: str, emails_dict: dict):
        self.email = email
        self.password = password
        self.provider = provider
        self.subject_prefix = subject_prefix

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


def clean(text):
    # clean text for creating a folder
    return "".join(c if c.isalnum() else "_" for c in text)
