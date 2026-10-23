import { defineCollection } from "astro:content";
import { z } from "astro/zod";
import { glob } from "astro/loaders";

const posts = defineCollection({
  loader: glob({ pattern: "**/*.{md,mdx}", base: "./src/content/posts" }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    date: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    author: z.object({ name: z.string(), url: z.string().url(), image: z.string() }).optional(),
    cover: z.object({ image: z.string(), alt: z.string() }).optional(),
    editorial: z.boolean().default(false),
    faq: z.array(z.object({ question: z.string(), answer: z.string() })).optional(),
    ctaEnd: z.object({ heading: z.string(), text: z.string(), links: z.array(z.object({ label: z.string(), url: z.string().url() })) }).optional(),
  }),
});

export const collections = { posts };
