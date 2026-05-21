package hu.nje.listapp.data.repositories;

import java.util.ArrayList;
import java.util.List;

import hu.nje.listapp.domain.Movie;

public class MockMovieRepository implements IMovieRepository {
    public List<Movie> getAll() {
        List<Movie> movies = new ArrayList<>();

        movies.add(new Movie("Dune: Part Two", "Sci-fi", 2024));
        movies.add(new Movie("Deadpool 3", "Action/Comedy", 2024));
        movies.add(new Movie("Kung Fu Panda 4", "Animation", 2024));
        movies.add(new Movie("Godzilla x Kong: The New Empire", "Action/Sci-fi", 2024));
        movies.add(new Movie("Ghostbusters: Frozen Empire", "Adventure/Comedy", 2024));
        movies.add(new Movie("Furiosa", "Action/Adventure", 2024));
        movies.add(new Movie("Joker: Folie à Deux", "Drama/Thriller", 2024));
        movies.add(new Movie("Inside Out 2", "Animation", 2024));
        movies.add(new Movie("Alien: Romulus", "Horror/Sci-fi", 2024));
        movies.add(new Movie("Kingdom of the Planet of the Apes", "Sci-fi", 2024));
        movies.add(new Movie("Garfield", "Animation/Comedy", 2024));
        movies.add(new Movie("Venom 3", "Action/Sci-fi", 2024));
        movies.add(new Movie("Mufasa: The Lion King", "Animation", 2024));
        movies.add(new Movie("Karate Kid", "Action/Drama", 2024));
        movies.add(new Movie("Gladiator 2", "Historical/Drama", 2024));
        movies.add(new Movie("Avatar 3", "Sci-fi/Adventure", 2025));
        movies.add(new Movie("Captain America: New World Order", "Action/Adventure", 2025));
        movies.add(new Movie("Mission: Impossible 8", "Action/Thriller", 2025));
        movies.add(new Movie("The Batman 2", "Action/Drama", 2025));
        movies.add(new Movie("Sonic the Hedgehog 3", "Adventure/Comedy", 2025));

        return movies;
    }
}
