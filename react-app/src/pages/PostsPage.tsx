import React from 'react';
import { useQuery } from '@tanstack/react-query';
import PostsTable from '../components/PostsTable';

// Type definition for a post from JSONPlaceholder.  Each post has an
// ``id``, ``title`` and ``body``.  See https://jsonplaceholder.typicode.com/posts
export interface Post {
  userId: number;
  id: number;
  title: string;
  body: string;
}

/**
 * Fetch posts from the JSONPlaceholder API.  This function is used by
 * React Query to populate the posts table.  If an error occurs, it
 * throws which will cause React Query to set the error state.
 */
async function fetchPosts(): Promise<Post[]> {
  const response = await fetch('https://jsonplaceholder.typicode.com/posts');
  if (!response.ok) {
    throw new Error('Failed to fetch posts');
  }
  return response.json();
}

/**
 * Page component that fetches and displays a list of posts.  It uses
 * React Query to manage server state and show loading and error states.
 */
const PostsPage: React.FC = () => {
  const { data: posts, isLoading, error } = useQuery<Post[]>(['posts'], fetchPosts);

  if (isLoading) {
    return <p>Loading posts…</p>;
  }

  if (error) {
    return <p className="text-red-600">Error loading posts.</p>;
  }

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">Posts</h2>
      {posts && <PostsTable posts={posts} />}
    </div>
  );
};

export default PostsPage;