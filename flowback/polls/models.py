# FlowBack was created and project lead by Loke Hagberg. The design was
# made by Lina Forsberg. Emilio Müller helped constructing Flowback.
# Astroneatech created the code. It was primarily financed by David
# Madsen. It is a decision making platform.
# Copyright (C) 2021  Astroneatech AB
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see https://www.gnu.org/licenses/.

from django.db import models

# Create your models here.
import os

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# Create your models here.
from taggit.managers import TaggableManager

from flowback.base.models import TimeStampedUUIDModel
from flowback.users.models import Group, User


class Post(TimeStampedUUIDModel):
    group = models.ForeignKey(Group,on_delete=models.CASCADE)
    description = models.TextField(_('Description'), blank=True)
    image = models.ImageField(null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.CASCADE,
                               related_name='posts')
    is_shown = models.BooleanField(_('Shown to user'), default=True, db_index=True)
    is_rejected = models.BooleanField(_('Is Rejected'), default=False, db_index=True)

    def __str__(self):
        return "%s - %s" % (self.is_shown, self.description)

    class Meta:
        verbose_name = _('Post')
        verbose_name_plural = _('Posts')


class PostComment(TimeStampedUUIDModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_comments')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='post_comments')
    comment = models.TextField(_('Post Comment'))

    class Meta:
        ordering = ('-created_at',)
        verbose_name = _('PostComment')
        verbose_name_plural = _('Post Comments')

    def __str__(self):
        return str(self.id)


class PollDocs(models.Model):
    file = models.FileField(upload_to='groups/polls/docs/')


class Poll(TimeStampedUUIDModel):

    def poll_docs_path(self, instance, filename):
        return os.path.join(
            "group_%d" % instance.group.id, "poll_%d" % instance.id, filename
        )

    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    title = models.CharField(_('Title'), max_length=256)
    description = models.TextField(_('Group Description'), null=True, blank=True)
    tag = TaggableManager()

    class Type(models.TextChoices):
        POLL = 'PO', _('poll')
        MISSION = 'MS', _('mission')
        EVENT = 'EV',  _('event')

    type = models.CharField(
        max_length=2,
        choices=Type.choices,
        default=Type.POLL
    )

    success = models.BooleanField(default=False)
    files = models.ManyToManyField(PollDocs, related_name='poll_documents')
    accepted = models.BooleanField(default=True)
    accepted_at = models.DateTimeField(_('Request accepted time'), null=True, blank=True)
    votes_counted = models.BooleanField(default=False)  # Determines if the counter proposals have had their votes counted
    start_time = models.DateTimeField(_('Start time'))
    end_time = models.DateTimeField(_('End time'))
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='poll_created_by')
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='poll_modified_by')


class PollUserDelegate(TimeStampedUUIDModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='+')
    delegator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='delegate_user_id')

    class Meta:
        unique_together = ('user', 'group', 'delegator')


class PollVotes(TimeStampedUUIDModel):
    UP_VOTE = 'upvote'
    DOWN_VOTE = 'downvote'
    VOTING_TYPE_CHOICES = (
        (UP_VOTE, _('Up vote')),
        (DOWN_VOTE, _('Down vote')),
    )

    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vote_type = models.CharField(choices=VOTING_TYPE_CHOICES, max_length=25)


class PollComments(TimeStampedUUIDModel):
    comment = models.TextField(_('Poll Comments'))
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    edited = models.BooleanField(default=False)
    likes = models.ManyToManyField(User, related_name='likes_by')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_created_by')
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_modified_by')


class PollBookmark(TimeStampedUUIDModel):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)


class PollCounterProposal(TimeStampedUUIDModel):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Type(models.TextChoices):
        DEFAULT = 'DEFAULT', _('Default')
        DROP = 'DROP', _('Drop')

    type = models.CharField(
        max_length=30,
        choices=Type.choices,
        default=Type.DEFAULT
    )

    proposal = models.TextField()
    final_score = models.IntegerField(null=True, blank=True)
    file = models.FileField(upload_to='groups/polls/proposal/', blank=True, null=True)

    class Meta:
        unique_together = ('poll', 'user')


class PollCounterProposalsIndex(TimeStampedUUIDModel):
    counter_proposal = models.ForeignKey(PollCounterProposal, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    priority = models.IntegerField()
    is_positive = models.BooleanField()  # Whether the user votes for or against the counter-proposal

    class Meta:
        unique_together = ('counter_proposal', 'user', 'priority', 'is_positive')


class PollCounterProposalComments(TimeStampedUUIDModel):
    comment = models.TextField(_('Counter Proposal Comments'))
    counter_proposal = models.ForeignKey(PollCounterProposal, on_delete=models.CASCADE)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    edited = models.BooleanField(default=False)
    likes = models.ManyToManyField(User, related_name='counter_proposal_likes_by')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='counter_proposal_comment_created_by')
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='counter_proposal_comment_modified_by')
