# A Dockerfile rather than Nixpacks: the JDK version is explicit, the layers are
# stable, and the image built in CI is byte-for-byte the one that runs on
# Railway.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build

# Dependencies resolve in their own layer, so a source-only change does not
# re-download the world.
COPY pom.xml .
RUN mvn -B -q dependency:go-offline

COPY src ./src
RUN mvn -B -q clean package -DskipTests

FROM eclipse-temurin:21-jre-alpine AS runtime
WORKDIR /app

# Never run as root. Alpine's adduser flags differ from Debian's.
RUN addgroup -S app && adduser -S -G app app
COPY --from=build --chown=app:app /build/target/accounts-*.jar /app/accounts.jar
USER app

EXPOSE 8080

# Container-aware heap sizing: the JVM reads the cgroup limit rather than the
# host's total memory, which is what makes it OOM on a small Railway instance.
ENV JAVA_OPTS="-XX:MaxRAMPercentage=75 -XX:+ExitOnOutOfMemoryError"

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/accounts.jar"]
