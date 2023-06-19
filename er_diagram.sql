-- DBML (Database Markup Language) to build ER Diagram of this project
-- https://dbdiagram.io/home

Table album {
	album_id string [PK]
	album_name string
	release_date date
	total_track int
}

Table track {
	track_id string [PK]
	track_name string
	duration float
	popularity int
	album_id string
	artist_id string
}

Table artist {
	artist_id string [PK]
	artist_name string
}

Ref track_album {
	track.album_id - album.album_id
}

Ref track_artist {
	track.artist_id - artist.artist_id
}
