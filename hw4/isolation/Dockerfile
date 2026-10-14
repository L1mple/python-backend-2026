ARG PYTHON_VERSION=3.13
FROM eclipse-temurin:21-jre AS java

FROM python:${PYTHON_VERSION}-slim-bookworm
COPY --from=java /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="${JAVA_HOME}/bin:${PATH}"
WORKDIR /lab
ADD https://repo.maven.apache.org/maven2/com/h2database/h2/2.5.252/h2-2.5.252.jar /lab/h2.jar
RUN echo '90b11dc413da82070ef15fc943282c1408e6ffd34fa68998335fea8603b5ff20  h2.jar' | sha256sum -c -
COPY runner-requirements.txt .
RUN pip install --no-cache-dir -r runner-requirements.txt
COPY runner.py test_runner.py ./
ENTRYPOINT ["python", "/lab/runner.py"]
CMD ["/output/events.jsonl"]
