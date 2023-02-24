FROM alpine:3.15

# Install required packages
RUN apk add --update --no-cache bash busybox-suid

# Install python/pip
RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python
RUN python3 -m ensurepip --upgrade
ENV PYTHONUNBUFFERED=1
# install any Python requirements used by the jobs
RUN pip3 install requests 

WORKDIR /usr/scheduler

# Copy files
COPY notify.py .
COPY crontab .
COPY start.sh .

RUN chmod 0644 ./crontab

# create cron.log file
RUN touch /var/log/cron.log

# Run cron on container startup
CMD ["./start.sh"]