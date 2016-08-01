# Django Amber

[![Build Status](https://travis-ci.org/inglesp/django-amber.svg?branch=master)](https://travis-ci.org/inglesp/django-amber)

Harness the power of Django to build your static sites!

## Status

Alpha-ish.  Django Amber is not yet used in production anywhere.


## Installation

Install Django Amber with `pip`:

    pip install django-amber


## Usage

### The basic idea

Django Amber is a static site generator, in the mould of
[Jekyll](https://jekyllrb.com/) or [Pelican](http://docs.getpelican.com/)

With Django Amber, you build your website using Django, making use of the full
Django toolkit: models, views, urlconfs, templates, tests, and so on.  Django
Amber then provides a way to dump the dynamically generated contents of your
site to a tree of static files on the filesystem, so that they can be served by
your favourite webserver or static site host.

Additionally, instead of storing your data in a database, your data is
serialized to files on the filesystem.  This means that you can keep your data
under version control, and benefit from all the tooling which that brings.
Each model instance is serialized to its own file.  Serialization is documented
under "Models" below.


### Management commands

Django Amber provides several management commands for managing your
application's data.


#### `buildsite`

You should use this command to generate a static copy of your website's pages,
so that it can be served by a webserver or static site host.

This command first runs the `loadpages` command, to populate the application's
database.  It then starts a local development server (via `runserver`), and
crawls the site, following every link starting at `/`.

The crawled pages are written to the `output` directory.

Additionally, if the `DJANGO_AMBER_CNAME` setting is set, a file is written to
the `output` directory whose contents is the value of this setting.  This is
useful for deploying to GitHub Pages.


#### `serve`

You should use this command in development, as a beefed-up version of
`runserver`.

This command takes an optional positional argument, the port on which to run
the server.  By default, this is `8000`.

This command starts a local development server (via `runserver`) and serves the
application as normal.

Before the server starts, it runs the `loadpages` command to populate the
application's database from the files serialized on the filesystem.

While the server is running, this command watches for any changes to the
serialized files on the filesystem, and updates the application's database
accordingly.


#### `loadpages`

You probably won't need need to invoke this command directly.

This command deserializes the contents of the filesystem, and loads objects
into the application's database.


#### `dumppages`

You probably won't need need to invoke this command directly.

This command serializes the contents of the application's database to the
filesystem.


### Models

All models whose data is serialized to the filesystem must inherit either from
`ModelWithContent` or `ModelWithoutContent`, which are [abstract base
classes](https://docs.djangoproject.com/en/1.9/topics/db/models/#abstract-base-classes)
defined in `django_amber.models`.

What follows is a description of these classes, including the fields they
provide to their subclasses, and details of instances of these classes are
serialized.  It is probably clearer to read the example later on.


#### `django_amber.models.ModelWithContent`

Subclasses of `ModelWithContent` are for models whose instances represent
objects with a significant amount of content, for instance a whole web page, a
news article, or a blog post.

Subclasses inherit the following fields:

* `key`: A `CharField` whose value identifies the model instance uniquely.
  This is used as the base of the filename when the model instance is
  serialized to the filesystem, and is also used when to identify related models
  (see below).
* `content`: A `TextField` whose value is the content corresponding to the page
  in question.
* `content_format`: A `CharField` whose value is the file extension
  corresponding to the format of the content.  For instance, if the content is
  [Markdown](https://daringfireball.net/projects/markdown/), the value should
  be `"md"`.  This is used as the file extension when the model instance is
  serialized to the filesystem.

Subclasses can define any other fields as required.

By default, instances of subclasses of `ModelWithContent` will be serialized to
the filesystem at `[app_label]]/data/[model_name]/[key].[content_format]`.
This can be overridden by setting the `dump_path_dir` class variable.  See the
`Article` model in `tests.models.py` for an example of this.

The file containing a serialized model instance will have two parts.  Firstly,
all fields, except for the three mentioned above, are serialized as YAML.
`ForeignKey`s and `ManyToManyField`s are handled as described below.  Then
follow three dashes (`---`), and then follows the value of the `content` field.


#### `django_amber.models.ModelWithoutContent`

Subclasses of `ModelWithoutContent` are for models whose instances represent
objects that do not have a significant amount of content.

Subclasses inherit the following field:

* `key`: A `CharField` whose value identifies the model instance uniquely.
  This is used as the base of the filename when the model instance is
  serialized to the filesystem, and is also used when to identify related models
  (see below).

Subclasses can define any other fields as required.

By default, instances of subclasses of `ModelWithContent` will be serialized to
the filesystem at `[app_label]]/data/[model_name]/[key].yml`.  This can be
overridden by setting the `dump_path_dir` class variable.  See the
`Article` model in `tests.models.py` for an example of this.

The file containing a serialized model instance contains all fields, except for
`key`, serialized as YAML.  `ForeignKey`s and `ManyToManyField`s are handled as
described below.


#### Relationships between models

This is definitely easier explained by example... see below.

If model `A` has a `ForeignKey` field to model `B`, when an instance `a` of `A`
is serialized, the serialized value of `b` will be `a.b.key`.

Similarly, if model `A` has a `ManyToManyField` field to model `C`, when an
instance `a` of `A` is serialized, the serialized value of `cs` will be the
list `[c.key for c in a.cs]`.

To ensure that objects can be deserialized correctly, all `ForeignKey` fields
must have `null` set to `True`.


### Example

Suppose we want to build a site that displays articles on a range of topics.
Each article has an author, and may have many tags.

We have the following three models in an app called `myapp`.


    class Article(ModelWithContent):
        title = models.CharField(max_length=255)
        author = models.ForeignKey('Author', null=True)
        tags = models.ManyToManyField('Tag', related_name='articles')

    class Author(ModelWithoutContent):
        name = models.CharField(max_length=255)
        email = models.EmailField()

    class Tag(ModelWithoutContent):
        name = models.CharField(max_length=255)
        description = models.CharField(max_length=255)


We can create instances of these models by creating some files on the
filesystem:

```
# myapp/pages/article/django.md
author: jane
tags:
- django
title: All about Django
---
This is an article about *Django*.
```

```
# myapp/metadata/author/jane.yml
name: Jane Smith
email: jane@example.com
```

```
# myapp/metadata/tag/django.yml
name: Django
description: Django is the web framework for perfectionists with deadlines
```

(Alternatively, we could populate the Django database via eg the admin, and
then run the `dumppages` command to write the data to the filesystem.)


## Development

Run tests with `tox`.


## About the name

[Thales of Miletus](https://en.wikipedia.org/wiki/Thales) used amber to
generate static electricity.
