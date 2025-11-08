import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams } from '@tanstack/react-router';
import type { Post } from './PostsPage';

/**
 * Fetch a single post from the JSONPlaceholder API.  Accepts the post
 * ``id`` as a parameter and returns a ``Post`` object.  Throws on
 * error.
 */
async function fetchPost(id: string): Promise<Post> {
  const response = await fetch(`https://jsonplaceholder.typicode.com/posts/${id}`);
  if (!response.ok) {
    throw new Error('Failed to fetch post');
  }
  return response.json();
}

/**
 * Page component for displaying a single post.  It reads the ``id`` from
 * the router parameters and uses React Query to fetch the post data.
 */
const PostPage: React.FC = () => {
  // ``useParams`` from TanStack Router gives access to dynamic route
  // parameters.  Here we extract the ``id`` from ``/posts/:id``.
  const { id } = useParams({
    from: '/posts/:id',
    select: (params) => params.id as string,
  });

  const { data: post, isLoading, error } = useQuery<Post>(['post', id], () => fetchPost(id));

  if (isLoading) {
    return <p>Loading post…</p>;
  }

  if (error || !post) {
    return <p className="text-red-600">Error loading post.</p>;
  }

  return (
    <article>
      <h2 className="text-2xl font-semibold mb-2">{post.title}</h2>
      <p className="mb-4 text-gray-700">{post.body}</p>
      <a href="/" className="text-blue-600 hover:underline">← Back to posts</a>
    </article>
  );
};

export default PostPage;