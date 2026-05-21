package hu.nje.listapp.data;

import hu.nje.listapp.data.entities.Movie;

public class DatabaseInitializer {
    private final MovieDatabase database;

    public DatabaseInitializer(MovieDatabase database) {
        this.database = database;
    }

    public void populateDatabase() {
        insertMovies();
    }

    private void insertMovies() {
        database.movieDao().insertMovie(new Movie(1, "Dune: Part Two", "Sci-fi", 2024));
        database.movieDao().insertMovie(new Movie(2, "Deadpool 3", "Action/Comedy", 2024));
        database.movieDao().insertMovie(new Movie(3, "Kung Fu Panda 4", "Animation", 2024));
        database.movieDao().insertMovie(new Movie(4, "Godzilla x Kong: The New Empire", "Action/Sci-fi", 2024));
        database.movieDao().insertMovie(new Movie(5, "Ghostbusters: Frozen Empire", "Adventure/Comedy", 2024));
        database.movieDao().insertMovie(new Movie(6, "Furiosa", "Action/Adventure", 2024));
        database.movieDao().insertMovie(new Movie(7, "Joker: Folie à Deux", "Drama/Thriller", 2024));
        database.movieDao().insertMovie(new Movie(8, "Inside Out 2", "Animation", 2024));
        database.movieDao().insertMovie(new Movie(9, "Alien: Romulus", "Horror/Sci-fi", 2024));
        database.movieDao().insertMovie(new Movie(10, "Kingdom of the Planet of the Apes", "Sci-fi", 2024));
        database.movieDao().insertMovie(new Movie(11, "Garfield", "Animation/Comedy", 2024));
        database.movieDao().insertMovie(new Movie(12, "Venom 3", "Action/Sci-fi", 2024));
        database.movieDao().insertMovie(new Movie(13, "Mufasa: The Lion King", "Animation", 2024));
        database.movieDao().insertMovie(new Movie(14, "Karate Kid", "Action/Drama", 2024));
        database.movieDao().insertMovie(new Movie(15, "Gladiator 2", "Historical/Drama", 2024));
        database.movieDao().insertMovie(new Movie(16, "Avatar 3", "Sci-fi/Adventure", 2025));
        database.movieDao().insertMovie(new Movie(17, "Captain America: New World Order", "Action/Adventure", 2025));
        database.movieDao().insertMovie(new Movie(18, "Mission: Impossible 8", "Action/Thriller", 2025));
        database.movieDao().insertMovie(new Movie(19, "The Batman 2", "Action/Drama", 2025));
        database.movieDao().insertMovie(new Movie(20, "Sonic the Hedgehog 3", "Adventure/Comedy", 2025));
    }
}
