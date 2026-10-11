FROM eclipse-temurin:21-jdk AS build
WORKDIR /lab
RUN curl -fsSL https://repo.maven.apache.org/maven2/com/h2database/h2/2.5.252/h2-2.5.252.jar -o h2.jar \
    && echo '90b11dc413da82070ef15fc943282c1408e6ffd34fa68998335fea8603b5ff20  h2.jar' | sha256sum -c -
COPY IsolationLab.java .
RUN javac --release 21 -Xlint:all -Werror IsolationLab.java

FROM eclipse-temurin:21-jre
WORKDIR /lab
COPY --from=build /lab/h2.jar .
COPY --from=build /lab/*.class ./
ENTRYPOINT ["java", "-cp", "/lab:/lab/h2.jar", "IsolationLab"]
CMD ["/output/events.jsonl"]
