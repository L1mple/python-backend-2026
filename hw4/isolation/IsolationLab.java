import java.io.IOException;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

/** Runs six coordinated read-anomaly experiments against H2. */
public final class IsolationLab {
    private static final int TIMEOUT_SECONDS = 15;
    private static final List<Scenario> SCENARIOS = List.of(
            new Scenario("dirty_ru", "READ_UNCOMMITTED", Connection.TRANSACTION_READ_UNCOMMITTED, true, false, 200),
            new Scenario("dirty_rc", "READ_COMMITTED", Connection.TRANSACTION_READ_COMMITTED, true, false, 100),
            new Scenario("nonrepeatable_rc", "READ_COMMITTED", Connection.TRANSACTION_READ_COMMITTED, false, false, 200),
            new Scenario("nonrepeatable_rr", "REPEATABLE_READ", Connection.TRANSACTION_REPEATABLE_READ, false, false, 100),
            new Scenario("phantom_rr", "REPEATABLE_READ", Connection.TRANSACTION_REPEATABLE_READ, false, true, 1),
            new Scenario("phantom_serializable", "SERIALIZABLE", Connection.TRANSACTION_SERIALIZABLE, false, true, 1)
    );

    private final Journal journal;

    private IsolationLab(Journal journal) {
        this.journal = journal;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("usage: IsolationLab /output/events.jsonl");
        }
        try (Journal journal = Journal.open(Path.of(args[0]))) {
            IsolationLab lab = new IsolationLab(journal);
            for (Scenario scenario : SCENARIOS) {
                lab.run(scenario);
            }
        }
        System.out.println("H2 2.5.252: all six isolation assertions passed");
    }

    private void run(Scenario scenario) throws Exception {
        String url = "jdbc:h2:mem:" + scenario.name() + ";DB_CLOSE_DELAY=-1;LOCK_TIMEOUT=5000";
        try (Connection setup = DriverManager.getConnection(url); Statement statement = setup.createStatement()) {
            if (!setup.getMetaData().getDatabaseProductVersion().startsWith("2.5.252")) {
                throw new IllegalStateException("expected H2 2.5.252, got " + setup.getMetaData().getDatabaseProductVersion());
            }
            statement.execute("CREATE TABLE accounts (id INT PRIMARY KEY, balance INT NOT NULL)");
            statement.execute("INSERT INTO accounts VALUES (1, 100)");
        }

        CountDownLatch firstRead = new CountDownLatch(1);
        CountDownLatch changed = new CountDownLatch(1);
        CountDownLatch secondRead = new CountDownLatch(1);
        CountDownLatch finished = new CountDownLatch(1);
        ExecutorService workers = Executors.newFixedThreadPool(2);
        try {
            Future<?> reader = workers.submit(() -> {
                read(scenario, url, firstRead, changed, secondRead, finished);
                return null;
            });
            Future<?> writer = workers.submit(() -> {
                write(scenario, url, firstRead, changed, secondRead, finished);
                return null;
            });
            reader.get(TIMEOUT_SECONDS * 2, TimeUnit.SECONDS);
            writer.get(TIMEOUT_SECONDS * 2, TimeUnit.SECONDS);
            journal.record(scenario, "LAB", "PASS", scenario.expected());
        } finally {
            workers.shutdownNow();
            if (!workers.awaitTermination(TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
                throw new IllegalStateException("transaction workers did not terminate: " + scenario.name());
            }
        }
    }

    private void read(Scenario scenario, String url, CountDownLatch firstRead, CountDownLatch changed,
                      CountDownLatch secondRead, CountDownLatch finished) throws Exception
    {
        try (Connection connection = transaction(url, scenario)) {
            journal.record(scenario, "T1", "BEGIN");
            int initial = scalar(connection, scenario);
            require(initial, scenario.phantom() ? 1 : 100, scenario.name() + " initial read");
            journal.record(scenario, "T1", "READ_1", initial);
            firstRead.countDown();

            await(changed, scenario.name() + " writer change");
            int observed = scalar(connection, scenario);
            journal.record(scenario, "T1", "READ_2", observed);
            require(observed, scenario.expected(), scenario.name() + " second read");
            secondRead.countDown();

            if (scenario.dirty()) {
                await(finished, scenario.name() + " writer rollback");
                int restored = scalar(connection, scenario);
                journal.record(scenario, "T1", "READ_AFTER_ROLLBACK", restored);
                require(restored, 100, scenario.name() + " rollback visibility");
            }
            connection.commit();
            journal.record(scenario, "T1", "COMMIT");
        }
    }

    private void write(Scenario scenario, String url, CountDownLatch firstRead, CountDownLatch changed,
                       CountDownLatch secondRead, CountDownLatch finished) throws Exception
    {
        try (Connection connection = transaction(url, scenario); Statement statement = connection.createStatement()) {
            journal.record(scenario, "T2", "BEGIN");
            await(firstRead, scenario.name() + " reader snapshot");
            String sql = scenario.phantom()
                    ? "INSERT INTO accounts VALUES (2, 150)"
                    : "UPDATE accounts SET balance = 200 WHERE id = 1";
            require(statement.executeUpdate(sql), 1, scenario.name() + " affected rows");
            journal.record(scenario, "T2", scenario.phantom() ? "INSERT" : "UPDATE", scenario.phantom() ? 150 : 200);

            if (scenario.dirty()) {
                changed.countDown();
                await(secondRead, scenario.name() + " dirty observation");
                connection.rollback();
                journal.record(scenario, "T2", "ROLLBACK");
                finished.countDown();
            } else {
                connection.commit();
                journal.record(scenario, "T2", "COMMIT");
                changed.countDown();
            }
        }
    }

    private static Connection transaction(String url, Scenario scenario) throws SQLException {
        Connection connection = DriverManager.getConnection(url);
        try {
            connection.setTransactionIsolation(scenario.level());
            connection.setAutoCommit(false);
            require(connection.getTransactionIsolation(), scenario.level(), scenario.name() + " isolation level");
            return connection;
        } catch (SQLException | RuntimeException failure) {
            connection.close();
            throw failure;
        }
    }

    private static int scalar(Connection connection, Scenario scenario) throws SQLException {
        String sql = scenario.phantom()
                ? "SELECT id, balance FROM accounts WHERE balance >= 100 ORDER BY id"
                : "SELECT balance FROM accounts WHERE id = 1";
        try (Statement statement = connection.createStatement()) {
            statement.setQueryTimeout(TIMEOUT_SECONDS);
            try (ResultSet result = statement.executeQuery(sql)) {
                if (scenario.phantom()) {
                    int count = 0;
                    while (result.next()) {
                        count++;
                    }
                    return count;
                }
                if (!result.next()) {
                    throw new IllegalStateException("missing scalar result: " + scenario.name());
                }
                return result.getInt(1);
            }
        }
    }

    private static void await(CountDownLatch latch, String phase) throws InterruptedException {
        if (!latch.await(TIMEOUT_SECONDS, TimeUnit.SECONDS)) {
            throw new IllegalStateException("coordination timeout: " + phase);
        }
    }

    private static void require(int actual, int expected, String phase) {
        if (actual != expected) {
            throw new IllegalStateException(phase + ": expected " + expected + ", observed " + actual);
        }
    }

    private record Scenario(String name, String isolation, int level, boolean dirty, boolean phantom, int expected) {}

    /** Writes globally ordered transaction events with monotonic elapsed time. */
    private static final class Journal implements AutoCloseable {
        private final PrintWriter output;
        private final long started;
        private int sequence;

        private Journal(PrintWriter output, long started) {
            this.output = output;
            this.started = started;
        }

        private static Journal open(Path path) throws IOException {
            Files.createDirectories(path.toAbsolutePath().getParent());
            return new Journal(new PrintWriter(Files.newBufferedWriter(path)), System.nanoTime());
        }

        private void record(Scenario scenario, String transaction, String event) {
            record(scenario, transaction, event, "null");
        }

        private void record(Scenario scenario, String transaction, String event, int value) {
            record(scenario, transaction, event, Integer.toString(value));
        }

        private synchronized void record(Scenario scenario, String transaction, String event, String value) {
            long elapsed = System.nanoTime() - started;
            output.printf(java.util.Locale.ROOT,
                    "{\"seq\":%d,\"case\":\"%s\",\"isolation\":\"%s\",\"tx\":\"%s\",\"event\":\"%s\",\"value\":%s,\"elapsed_ms\":%.6f}%n",
                    ++sequence, scenario.name(), scenario.isolation(), transaction, event, value, elapsed / 1_000_000.0
            );
            output.flush();
            if (output.checkError()) {
                throw new IllegalStateException("cannot write transaction journal");
            }
        }

        @Override
        public void close() {
            output.close();
        }
    }
}
