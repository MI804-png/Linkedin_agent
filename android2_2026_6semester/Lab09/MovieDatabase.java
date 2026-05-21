package hu.nje.listapp.data;

import android.content.Context;

import androidx.annotation.NonNull;
import androidx.room.Database;
import androidx.room.Room;
import androidx.room.RoomDatabase;
import androidx.sqlite.db.SupportSQLiteDatabase;

import java.util.concurrent.Executors;

import hu.nje.listapp.data.daos.MovieDao;
import hu.nje.listapp.data.entities.Movie;

@Database(entities = {Movie.class}, version = 1)
public abstract class MovieDatabase extends RoomDatabase {
    private static volatile MovieDatabase INSTANCE;

    public abstract MovieDao movieDao();

    public static MovieDatabase getDatabase(final Context context) {
        if (INSTANCE == null) {
            synchronized (MovieDatabase.class) {
                if (INSTANCE == null) {
                    INSTANCE = Room.databaseBuilder(context.getApplicationContext(),
                                    MovieDatabase.class, "movie_database")
                            .addCallback(new RoomDatabase.Callback() {
                                @Override
                                public void onCreate(@NonNull SupportSQLiteDatabase db) {
                                    super.onCreate(db);
                                    Executors.newSingleThreadExecutor().execute(() -> {
                                        MovieDatabase database = getDatabase(context);
                                        DatabaseInitializer initializer = new DatabaseInitializer(database);
                                        initializer.populateDatabase();
                                    });
                                }
                            })
                            .build();
                }
            }
        }
        return INSTANCE;
    }
}
