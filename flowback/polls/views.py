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

import datetime
from itertools import groupby
import json
import copy

from random import randint
from django.core.mail import send_mail
from django.db.models import Q
from rest_framework import decorators, viewsets, status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import *
from django.core.paginator import Paginator
from django.db.models import Count

from flowback.response import Created, BadRequest, NotFound
from flowback.response import Ok
from flowback.response_handler import success_response, failed_response
from flowback.users.models import Group, OnboardUser
from flowback.users.models import User
from flowback.polls.models import Poll, PollDocs, PollVotes, PollComments, PollBookmark,\
    PollCounterProposal, PollCounterProposalComments, PollCounterProposalsIndex, PollUserDelegate
from flowback.users.serializer import UserGroupCreateSerializer, MyGroupSerializer, AddParticipantSerializer, \
    OnboardUserFirstSerializer, OnboardUserSecondSerializer, GroupParticipantSerializer, CreateGroupRequestSerializer, \
    UpdateGroupRequestSerializer
from flowback.users.serializer import UserSerializer, SimpleUserSerializer, UserRegistrationSerializer, \
    GroupDetailsSerializer
from flowback.polls.serializer import GroupPollCreateSerializer, GetGroupPollsListSerializer, \
    GroupPollDetailsSerializer, \
    CreatePollCommentSerializer, GetPollCommentsSerializer, GetPendingPollListSerializer, GetBookmarkPollListSerializer, \
    GroupPollUpdateSerializer, CreatePollCounterProposalSerializer, GetPollCounterProposalDetailsSerializer, \
    CreateCounterProposalCommentSerializer, DelegatorSerializer


class GroupPollViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @decorators.action(detail=False, methods=['post'], url_path="create_poll")
    def create_group_poll(self, request, *args, **kwargs):
        try:
            data = request.data
            poll_data = data.get('poll_details')
            poll_docs = data.getlist('poll_docs')
            # serializer for create poll
            serializer = GroupPollCreateSerializer(data=json.loads(poll_data))
            if serializer.is_valid(raise_exception=False):
                # get group object by id
                group = Group.objects.filter(id=serializer.data.get('group')).first()
                if group.poll_approval == 'direct_approve':
                    accepted = True
                else:
                    accepted = False
                # create or get the poll object
                poll, created = Poll.objects.get_or_create(created_by=request.user,
                                                           modified_by=request.user,
                                                           group=serializer.validated_data.get('group'),
                                                           title=serializer.validated_data.get('title'),
                                                           description=serializer.validated_data.get('description'),
                                                           type=serializer.validated_data.get('type'),
                                                           start_time=datetime.datetime.now(),
                                                           end_time=serializer.validated_data.get('end_time'),
                                                           )
                if accepted:
                    poll.accepted = True
                    poll.accepted_at = datetime.datetime.now()
                else:
                    poll.accepted = False
                poll_details_json = json.loads(poll_data)
                if poll_details_json.get('tags'):
                    tags = poll_details_json.get('tags').split(' ')
                    # add tag inti poll object
                    for tag in tags:
                        poll.tag.add(tag)

                # create doc object and add it in poll files
                for doc in poll_docs:
                    doc = PollDocs.objects.create(file=doc)
                    poll.files.add(doc)

                poll.save()

                # return success response with poll id
                result = success_response(data={"poll": poll.id}, message="")
                return Created(result)
            # return response with serializer error
            result = failed_response(data=serializer.errors, message="")
            return BadRequest(result)
        except Exception as e:
            # return response with error occurred during exception
            result = failed_response(data=str(e), message="")
            return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="update_poll_details")
    def update_poll_details(self, request, *args, **kwargs):
        user = request.user
        data = request.data

        # get poll from poll id
        poll = Poll.objects.filter(id=data.get('poll')).first()
        if poll:
            group = poll.group
            # check the role of user
            if poll.created_by == user or user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():
                # create serializer for update the poll
                serializer = GroupPollUpdateSerializer(poll, data=data, partial=True, context={'request': self.request})
                if serializer.is_valid():
                    serializer.save()

                if data.get('tags'):
                    poll.tag.clear()
                    tags = data.get('tags').split(' ')
                    # add tags in poll
                    for tag in tags:
                        poll.tag.add(tag)
                poll.modified_by = request.user
                poll.save()
                # return success response
                result = success_response(data=None, message="")
                return Created(result)
            # return error response with user permission
            result = failed_response(data=None, message="You don't have to permission to update the poll details.")
            return BadRequest(result)
        # return error response with poll details
        result = failed_response(data=None, message="Poll does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="poll_bookmark")
    def poll_bookmark(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        # get poll by poll id
        poll = Poll.objects.filter(id=data.get('poll')).first()
        # check if poll exist otherwise throw error
        if poll:
            bookmark = data.get('bookmark')
            # get bookmark poll by user and poll
            poll_bookmark = PollBookmark.objects.filter(poll=poll, user=user).first()
            # if it is already bookmarked then delete it otherwise create bookmark object
            if poll_bookmark:
                if not bookmark:
                    poll_bookmark.delete()
            else:
                poll = PollBookmark.objects.create(poll=poll, user=user)
                poll.save()
            # return success response
            result = success_response(data=None, message="")
            return Created(result)
        result = failed_response(data=None, message="Poll does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['get'], url_path="get_bookmark_polls")
    def get_bookmark_polls(self, request, *args, **kwargs):
        user = request.user
        # get all bookmark poll filtered by logged in user
        polls = PollBookmark.objects.filter(user=user)
        serializer = GetBookmarkPollListSerializer(polls, many=True)
        result = success_response(data=serializer.data, message="")
        return Ok(result)

    @decorators.action(detail=False, methods=['post'], url_path="verify_pending_poll_list")
    def verify_pending_poll_list(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        # get group by id and if not exist then return error response
        group = Group.objects.filter(id=data.get('group')).first()
        if group:
            # check the role of user in group
            if user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():

                # get poll and create serializer for get json data
                polls = Poll.objects.filter(group=group, accepted=False)
                serializer = GetPendingPollListSerializer(polls, many=True)
                result = success_response(data=serializer.data, message="")
                return Created(result)
            # if user don't have permission then return error response
            result = failed_response(data=None, message="You don't have permission to get list of pending verification "
                                                        "polls.")
            return BadRequest(result)
        result = failed_response(data=None, message="Group does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="get_all_verify_pending_poll_list")
    def get_all_verify_pending_poll_list(self, request, *args, **kwargs):
        user = request.user
        # get all group where user is owner, admin or moderator
        groups = Group.objects.filter(Q(created_by=user) | Q(owners__in=[user]) | Q(admins__in=[user]) |
                                      Q(moderators__in=[user]))
        # get all polls with verification status is pending
        polls = Poll.objects.filter(group__in=groups, accepted=False)
        serializer = GetPendingPollListSerializer(polls, many=True)
        result = success_response(data=serializer.data, message="")
        return Ok(result)

    @decorators.action(detail=False, methods=['post'], url_path="verify_poll")
    def verify_poll(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        # get poll by poll id. if it does not exist then return the error response
        poll = Poll.objects.filter(id=data.get('poll')).first()
        if poll:
            group = poll.group
            # check the role of user in group and return error response if role doesn't match
            if user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():
                poll.accepted = True
                poll.accepted_at = datetime.datetime.now()
                poll.save()
                serializer = GroupPollDetailsSerializer(poll, context={'request': self.request})
                result = success_response(data=serializer.data, message="")
                return Created(result)
            result = failed_response(data=None, message="You don't have permission to verify the poll.")
            return BadRequest(result)
        result = failed_response(data=None, message="Poll does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="get_poll_list")
    def get_poll_list(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        response = dict()
        first_page = data.get('first_page')
        last_poll_created_at = data.get('last_poll_created_at', None)

        # get group by id and if does not exist then return error response
        group = Group.objects.filter(id=data.get('group_id')).first()
        if group:
            # get all the group where logged in user is a participant on that group
            part_of_group = Group.objects.filter(Q(owners__in=[user]) | Q(admins__in=[user]) | Q(moderators__in=[user]) |
                                                 Q(members__in=[user]) | Q(delegators__in=[user]),
                                                 id=data.get('group_id'))
            if part_of_group:
                if first_page:
                    # get all polls of particular group
                    polls = Poll.objects.filter(group=group).order_by('-created_at')
                    last_poll_created_at = polls.first().created_at if polls else None
                    response['last_poll_created_at'] = last_poll_created_at
                else:
                    polls = Poll.objects.filter(group=group, created_at__lte=last_poll_created_at)\
                        .order_by('-created_at') if last_poll_created_at else []

                page_number = data.get('page', 1)  # page number
                page_size = data.get('page_size', 10)  # size per page
                paginator = Paginator(polls, page_size)

                response['count'] = paginator.count
                response['total_page'] = len(paginator.page_range)
                response['next'] = paginator.page(page_number).has_next()
                response['previous'] = paginator.page(page_number).has_previous()

                # create serializer for get data page by page
                serializer = GetGroupPollsListSerializer(paginator.page(page_number), many=True, context={'request': self.request})
                response['data'] = serializer.data

                result = success_response(data=response, message="")
                return Created(result)
            result = failed_response(data=None, message="You are not a part of this group.")
            return BadRequest(result)
        result = failed_response(data=None, message="Group does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="get_poll_list")
    def get_poll_list(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        response = dict()
        first_page = data.get('first_page')
        last_poll_created_at = data.get('last_poll_created_at', None)

        # get group by id and if does not exist then return error response
        group = Group.objects.filter(id=data.get('group_id')).first()
        if group:
            # get all the group where logged in user is a participant on that group
            part_of_group = Group.objects.filter(Q(owners__in=[user]) | Q(admins__in=[user]) | Q(moderators__in=[user]) |
                                                 Q(members__in=[user]) | Q(delegators__in=[user]),
                                                 id=data.get('group_id'))
            if part_of_group:
                if first_page:
                    # get all polls of particular group
                    polls = Poll.objects.filter(group=group).order_by('-created_at')
                    last_poll_created_at = polls.first().created_at if polls else None
                    response['last_poll_created_at'] = last_poll_created_at
                else:
                    polls = Poll.objects.filter(group=group, created_at__lte=last_poll_created_at)\
                        .order_by('-created_at') if last_poll_created_at else []

                page_number = data.get('page', 1)  # page number
                page_size = data.get('page_size', 10)  # size per page
                paginator = Paginator(polls, page_size)

                response['count'] = paginator.count
                response['total_page'] = len(paginator.page_range)
                response['next'] = paginator.page(page_number).has_next()
                response['previous'] = paginator.page(page_number).has_previous()

                # create serializer for get data page by page
                serializer = GetGroupPollsListSerializer(paginator.page(page_number), many=True, context={'request': self.request})
                response['data'] = serializer.data

                result = success_response(data=response, message="")
                return Created(result)
            result = failed_response(data=None, message="You are not a part of this group.")
            return BadRequest(result)
        result = failed_response(data=None, message="Group does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="home_all_poll_list", permission_classes=[AllowAny])
    def get_all_poll_list(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        response = dict()
        poll_type = data.get('poll_type', 'MS')
        poll_created_before = data.get('poll_created_before', None)

        def user_in_group_query(include_public, **additional_args):
            allow_public = {}
            if include_public:
                allow_public = dict(group__public=include_public)

            return Q(**allow_public) | Q(
                Q(group__owners__in=[user]) | Q(group__admins__in=[user])
                | Q(group__moderators__in=[user]) | Q(group__members__in=[user])
                | Q(group__delegators__in=[user]), group__public=False, **additional_args)

        arguments = dict()
        if poll_created_before:
            arguments['created_at__lte'] = poll_created_before

        # Fetch Polls
        if user.id is None:
            arguments['group__public'] = True
            polls = Poll.objects.filter(**arguments).order_by('-created_at')

        else:
            extra_args = {}  # Custom Arguments
            if poll_type in Poll.Type.MISSION:
                extra_args = dict(type=Poll.Type.MISSION, success=True)

            polls = Poll.objects.filter(
                user_in_group_query(poll_type not in ['MS'], **extra_args),
                **arguments
            ).order_by('-created_at').distinct()

        # Paginate
        page_number = data.get('page', 1)  # page number
        page_size = data.get('page_size', 10)  # size of data per page
        paginator = Paginator(polls, page_size)

        response['count'] = paginator.count
        response['total_page'] = len(paginator.page_range)
        response['next'] = paginator.page(page_number).has_next()
        response['previous'] = paginator.page(page_number).has_previous()

        # Serialize
        serializer = GetGroupPollsListSerializer(paginator.page(page_number), many=True,
                                                 context={"request": self.request})
        response['data'] = serializer.data
        result = success_response(data=response, message="")
        return Ok(result)

    @decorators.action(detail=False, methods=['post'], url_path="poll_voting")
    def poll_voting(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        voting_type = data.get('voting_type')
        # get all group where user is participated
        participant = Group.objects.filter(Q(owners__in=[user]) | Q(admins__in=[user]) | Q(moderators__in=[user]) |
                                           Q(members__in=[user]), id=data.get('group'))
        if participant:
            # get pollvotes object by id and create new object if does not exist
            poll_vote = PollVotes.objects.filter(poll=data.get('poll'), user=user).first()
            if poll_vote:
                serializer = GroupPollDetailsSerializer(poll_vote.poll, context={'request': self.request})
                # if already voted the delete the vote otherwise save the vote details
                if poll_vote.vote_type == voting_type:
                    poll_vote.delete()
                else:
                    poll_vote.vote_type = voting_type
                    poll_vote.save()

            else:
                poll = Poll.objects.filter(id=data.get('poll')).first()
                poll_vote = PollVotes.objects.create(poll=poll, user=user, vote_type=voting_type)
                poll_vote.save()

                serializer = GroupPollDetailsSerializer(poll, context={'request': self.request})

            result = success_response(data=serializer.data, message="")
            return Ok(result)
        result = failed_response(data=None, message="You won't able to voting.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="poll_details")
    def poll_details(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        # get poll by id or return error response if poll does not exist
        poll = Poll.objects.filter(id=data.get('poll')).first()
        if poll:
            # get all public group or user participate on that group
            participant = Group.objects.filter(Q(public=True) | Q(owners__in=[user]) | Q(admins__in=[user]) | Q(moderators__in=[user]) |
                                               Q(members__in=[user]), id=data.get('group'))
            if participant:
                serializer = GroupPollDetailsSerializer(poll, context={'request': self.request})
                response_data = serializer.data
                # get all the comment of particular poll
                poll_comments = PollComments.objects.filter(poll=poll).order_by('-created_at')
                comment_serializer = GetPollCommentsSerializer(poll_comments, many=True, context={'request': self.request})
                # add comments and comment count in response data
                response_data['comments_details'] = dict()
                response_data['comments_details']['comments'] = comment_serializer.data
                response_data['comments_details']['total_comments'] = len(poll_comments)

                result = success_response(data=response_data, message="")
                return Ok(result)
            result = failed_response(data=None, message="You are not a part of this group.")
            return BadRequest(result)
        result = failed_response(data=None, message="Poll does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="delegate")
    def delegate(self, request, *args, **kwargs):  # TODO test
        user = request.user
        data = request.data
        delegator = User.objects.filter(id=data.get('delegator_id')).first()
        group = Group.objects.filter(id=data.get('group_id')).first()

        if delegator and group:
            # Check if delegator exists
            delegate_is_valid = group.delegators.filter(
                id=data.get('delegator_id', -1)
                ).first()
            user_is_group_member = Group.objects.filter(Q(owners__in=[user]) | Q(admins__in=[user]) |
                                                        Q(moderators__in=[user]) | Q(members__in=[user]) |
                                                        Q(delegators__in=[user]), id=data.get('group_id'))
            if delegate_is_valid and user_is_group_member:
                # Delete all poll votes
                PollUserDelegate.objects.filter(user=user, group=group).delete()
                PollCounterProposalsIndex.objects.filter(user=user, counter_proposal__poll__group=group).delete()
                PollUserDelegate.objects.create(user=user,
                                                group=group,
                                                delegator=delegator
                                                ).save()
                result = success_response(data=None, message="Votes has been delegated")
                return Created(result)
        result = failed_response(data=None, message="")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="remove_delegate")
    def remove_delegate(self, request, *args, **kwargs):  # TODO test
        user = request.user
        data = request.data
        keep_delegator_votes = data.get('keep_delegator_votes')
        group = Group.objects.filter(Q(owners__in=[user]) | Q(admins__in=[user]) |
                                                        Q(moderators__in=[user]) | Q(members__in=[user]) |
                                                        Q(delegators__in=[user]), id=data.get('group_id')).first()

        if group:
            # Check if delegator exists
            delegator = PollUserDelegate.objects.filter(
                user=user,
                group=group
            ).first()
            if delegator:
                # Copy delegator votes to user
                if keep_delegator_votes:
                    votes = copy.deepcopy(PollCounterProposalsIndex.objects.filter(
                        user=delegator.delegator,
                        counter_proposal__poll__group=group
                    ).all())
                    for i in range(len(votes)):
                        votes[i].user = user
                        votes[i].id = None
                    PollCounterProposalsIndex.objects.bulk_create(votes)
                # Delete all poll votes
                PollUserDelegate.objects.filter(user=user, group=group).delete()
                result = success_response(data=None, message="User successfully removed delegate")
                return Created(result)
            result = failed_response(data=None, message="User has no delegator attached to group")
            return BadRequest(result)
        result = failed_response(data=None, message="Group doesn't exist")
        return NotFound(result)

    @decorators.action(detail=False, methods=['post'], url_path="create_poll_comment")
    def create_poll_comment(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        # serializer for create comment object
        serializer = CreatePollCommentSerializer(data=data)
        if serializer.is_valid():
            comment = PollComments.objects.create(comment=serializer.validated_data.get('comment'),
                                                  poll=serializer.validated_data.get('poll'),
                                                  reply_to=serializer.validated_data.get('reply_to'),
                                                  created_by=user, modified_by=user)
            comment.save()
            serializer = GetGroupPollsListSerializer(comment.poll, context={'request': self.request})
            result = success_response(data=serializer.data, message="")
            return Created(result)
        result = failed_response(data=serializer.errors, message="")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="edit_poll_comment")
    def edit_poll_comment(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        # get poll comment by id or return the error response if comment does not exist
        poll_comment = PollComments.objects.filter(id=data.get('comment_id')).first()
        if poll_comment:
            group = poll_comment.poll.group
            # check permission for edit the poll comment
            if poll_comment.created_by == user or user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():
                poll_comment.comment = data.get('comment')
                poll_comment.modified_by = user
                poll_comment.edited = True
                poll_comment.save()

                serializer = GetGroupPollsListSerializer(poll_comment.poll, context={'request': self.request})
                result = success_response(data=serializer.data, message="Comment edited successfully.")
                return Created(result)
            result = failed_response(data=None, message="Only comment creator, owner of group or admins can edit"
                                                        " the comment")
            return BadRequest(result)
        result = failed_response(data=None, message="Poll comment does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="delete_poll_comment")
    def delete_poll_comment(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        # get poll comment by id or return the error response if comment does not exist
        comment = PollComments.objects.filter(id=data.get('comment')).first()
        if comment:
            poll = comment.poll
            group = comment.poll.group
            # check permission for delete the poll comment
            if comment.created_by == user or user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():
                comment.delete()
                serializer = GetGroupPollsListSerializer(poll, context={'request': self.request})
                result = success_response(data=serializer.data, message="Comment deleted successfully.")
                return Created(result)

            result = failed_response(data=None, message="Only comment creator, owner of group or admins can delete"
                                                        " the comment")
            return BadRequest(result)
        result = failed_response(data=None, message="Poll comment does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="get_poll_comments")
    def get_poll_comments(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        # get poll by id or return error response of poll does not exist
        poll = Poll.objects.filter(id=data.get('poll')).first()
        if poll:
            group = poll.group
            # check the role of user
            if user in group.owners.all() or user in group.admins.all() or user in group.moderators.all() or \
                    user in group.members.all() or user in group.delegators.all():
                comments = PollComments.objects.filter(poll=poll)
                # serializer for get all comments details in json
                serializer = GetPollCommentsSerializer(comments, many=True, context={'request': self.request})

                result = success_response(data=serializer.data, message="Get all poll successfully.")
                return Created(result)
            result = failed_response(data=None, message="You are not a part of this group.")
            return BadRequest(result)
        result = failed_response(data=None, message="Poll does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="like_dislike_poll_comment")
    def like_dislike_poll_comment(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        like = data.get('like', None)
        # get poll comment by id or return error response if comment does not exist
        poll_comment = PollComments.objects.filter(id=data.get('poll_comment')).first()
        if poll_comment:
            # if already liked then remove the like otherwise like the comment
            if like:
                poll_comment.likes.add(user)
                poll_comment.save()
            else:
                poll_comment.likes.remove(user)
                poll_comment.save()
            serializer = GetGroupPollsListSerializer(poll_comment.poll, context={'request': self.request})
            result = success_response(data=serializer.data, message="Comment deleted successfully.")
            return Created(result)
        result = failed_response(data=None, message="Comment does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="add_new_poll_docs")
    def add_new_poll_docs(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        # get poll object by id or return error response if poll does not exist
        poll = Poll.objects.filter(id=data.get('poll')).first()
        if poll:
            group = poll.group
            # check user permission for group
            if poll.created_by == user or user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():
                poll_docs = data.getlist('poll_docs', None)
                if poll_docs:
                    # create doc object and add it into the poll
                    for doc in poll_docs:
                        doc = PollDocs.objects.create(file=doc)
                        poll.files.add(doc)
                    poll.save()
                    result = success_response(data=None, message="")
                    return Created(result)
                result = failed_response(data=None, message="Please provide new documents.")
                return BadRequest(result)
            result = failed_response(data=None, message="You don't have to permission to add new poll docs.")
            return BadRequest(result)
        result = failed_response(data=None, message="Poll does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="remove_poll_doc")
    def remove_poll_doc(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        # get poll object by id or return error response if poll does not exist
        poll = Poll.objects.filter(id=data.get('poll')).first()
        if poll:
            group = poll.group
            # check user permission for group
            if poll.created_by == user or user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():
                poll_doc = data.get('poll_doc', None)
                if poll_doc:
                    # remove doc from poll
                    poll.files.remove(poll_doc)
                    poll.save()
                    result = success_response(data=None, message="")
                    return Created(result)
                result = failed_response(data=None, message="Please provide new documents.")
                return BadRequest(result)
            result = failed_response(data=None, message="You don't have to permission to add new poll docs.")
            return BadRequest(result)
        result = failed_response(data=None, message="Poll does not exist.")
        return BadRequest(result)

    # TODO make file not a requirement
    @decorators.action(detail=False, methods=['post'], url_path="add_counter_proposal")
    def add_counter_proposal(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        # get poll counter proposal filtered by user and poll
        proposal = PollCounterProposal.objects.filter(user=user, poll__id=data.get('poll'))
        if not proposal:
            # serializer for create counter proposal for poll
            serializer = CreatePollCounterProposalSerializer(data=data)
            if serializer.is_valid():
                serializer.save(user=user)
                result = success_response(data=serializer.data, message="Counter proposal created successfully.")
                return Created(result)
            result = failed_response(data=serializer.errors, message="")
            return BadRequest(result)
        result = failed_response(data=None, message="Proposal is already exist.")
        return BadRequest(result)

    def __poll_votes_check(self, poll: Poll):
        Poll.objects.filter(id=poll.id).update(start_time=datetime.datetime.now(), end_time=datetime.datetime.now() + datetime.timedelta(hours=1))

        # Counting Proposal Votes
        if poll.end_time <= datetime.datetime.now() and not poll.votes_counted:
            counter_proposals = PollCounterProposal.objects.filter(poll=poll).all()
            counter = {key.id: 0 for key in counter_proposals}
            for index, proposal in enumerate(counter_proposals):
                # Give final_score a value
                counter_proposals[index].final_score = 0

                group = proposal.poll.group
                c_indexes = PollCounterProposalsIndex.objects.filter(
                    counter_proposal=proposal).all()
                c_indexes = [list(g) for k, g in groupby(c_indexes, lambda x: x.user.id)]
                for user_c_indexes in c_indexes:
                    multiplier = 1

                    # Check if user is delegate
                    user = user_c_indexes[0].user
                    if user in group.delegators.all():
                        multiplier = len(PollUserDelegate.objects.filter(delegator=user, group=group).all())

                    # TODO priority is a constant, deleting a counter proposal doesn't change it's score,
                    # A solution would probably be to sort the proposals in priority order,
                    # and then to add a counter
                    for sub, c_index in enumerate(user_c_indexes):
                        if c_index.is_positive:
                            counter_proposals[index].final_score += (len(counter_proposals) - c_index.priority) \
                                                                     * multiplier

                        else:
                            counter_proposals[index].final_score += (c_index.priority - len(counter_proposals)) \
                                                                     * multiplier

            # Poll Type Checks
            if poll.type == Poll.Type.MISSION:
                top = counter_proposals.order_by('-final_score').first()
                if top.type != PollCounterProposal.Type.DROP:
                    poll.success = True
                    Poll.objects.update(poll, ['success'])

            PollCounterProposal.objects.bulk_update(counter_proposals, ['final_score'])
            Poll.objects.filter(id=poll.id).update(votes_counted=True)
        #
        # elif poll.votes_counted:
        #     raise Exception("Counter proposals has already been counted.")
        #
        # else:
        #     raise Exception("Poll has not been finished yet.")

    @decorators.action(detail=False, methods=['post'], url_path="get_all_counter_proposal")
    def get_all_counter_proposal(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        poll = Poll.objects.filter(id=data.get('poll')).first() if data.get('poll') else None
        if poll:
            self.__poll_votes_check(poll)
            # get counter proposal for poll filtered by user and poll
            proposals = PollCounterProposal.objects.filter(poll__id=poll.id).order_by('-created_at')
            # serializer for get details of counter proposal
            serializer = GetPollCounterProposalDetailsSerializer(proposals, many=True, context={'request': self.request})
            response_data = dict()
            response_data['counter_proposals'] = serializer.data
            user_to_index = user
            delegate = PollUserDelegate.objects.filter(user=user, group=poll.group).first()
            if delegate:
                response_data['delegator'] = {"username": user.username, "user_id": user.id}
                user_to_index = delegate.delegator
            user_proposal_index = PollCounterProposalsIndex.objects.filter(counter_proposal__poll_id=poll,
                                                                           user=user_to_index)
            if user_proposal_index:
                positive_proposal_index = [x.counter_proposal.id for x in sorted([x for x in user_proposal_index
                                                                                       if x.is_positive],
                                           key=lambda x: x.priority)]
                negative_proposal_index = [x.counter_proposal.id for x in sorted([x for x in user_proposal_index
                                                                                       if not x.is_positive],
                                           key=lambda x: x.priority)]
                response_data['positive_proposal_index'] = positive_proposal_index
                response_data['negative_proposal_index'] = negative_proposal_index

                # TODO make frontend support positive and negative proposal index instead of old standard
                response_data['proposal_indexes'] = {}
                for val, c_id in enumerate(positive_proposal_index):
                    response_data['proposal_indexes'][str(c_id)] = val + 1
                for val, c_id in enumerate(negative_proposal_index):
                    response_data['proposal_indexes'][str(c_id)] = -1 - val

            result = success_response(data=response_data, message="Counter proposal get successfully.")
            return Ok(result)

        result = failed_response(data=None, message="Pass poll parameter with poll id.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="get_user_delegator")
    def get_user_delegator(self, request, *args, **kwargs):  # TODO Adjust this to work with delegate system
        data = request.data
        user = request.user
        delegator = PollUserDelegate.objects.filter(user=user, group_id=data.get('group_id', -1)).first()
        if delegator:
            group = Group.objects.filter(Q(owners__in=[user]) | Q(admins__in=[user]) |
                                         Q(moderators__in=[user]) | Q(members__in=[user]) |
                                         Q(delegators__in=[user]), id=data.get('group_id')).first()
            if group:
                return_data = {'delegator_id': delegator.delegator_id}
                result = success_response(data=return_data, message="Counter proposal get successfully.")
                return Created(result)
            result = failed_response(data=None, message="Group not found")
            return NotFound(result)
        result = failed_response(data=None, message="User has no delegator attached to group")
        return NotFound(result)

    @decorators.action(detail=False, methods=['post'], url_path="get_counter_proposal")
    def get_counter_proposal(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        poll = Poll.objects.filter(id=data.get('poll')).first() if data.get('poll') else None
        if poll:
            self.__poll_votes_check(poll)
            # get counter proposal for poll filtered by user and poll
            proposal = PollCounterProposal.objects.filter(poll__id=poll.id, user=user).first()
            # serializer for get details of counter proposal of poll
            serializer = GetPollCounterProposalDetailsSerializer(proposal, context={'request': self.request})
            result = success_response(data=serializer.data, message="Counter proposal get successfully.")
            return Created(result)

        result = failed_response(data=None, message="Please pass poll parameter with poll id.")
        return BadRequest(result)

    def __update_proposal_indexes(self, user: User, poll: Poll, positive_proposal_index: list,
                                  negative_proposal_index: list):
        positive_proposal_index_check = PollCounterProposal.objects.filter(id__in=positive_proposal_index, poll=poll)
        negative_proposal_index_check = PollCounterProposal.objects.filter(id__in=negative_proposal_index, poll=poll)
        if len(positive_proposal_index_check) == len(positive_proposal_index) \
                and len(negative_proposal_index_check) == len(negative_proposal_index)\
                and not set(positive_proposal_index) & set(negative_proposal_index):

            PollCounterProposalsIndex.objects.filter(counter_proposal__poll=poll, user=user).delete()
            PollCounterProposalsIndex.objects.bulk_create(
                [PollCounterProposalsIndex(counter_proposal_id=c_id,
                                           user=user,
                                           priority=i,
                                           is_positive=True) for i, c_id in enumerate(positive_proposal_index)] +
                [PollCounterProposalsIndex(counter_proposal_id=c_id,
                                           user=user,
                                           priority=i,
                                           is_positive=False) for i, c_id in enumerate(negative_proposal_index)]
            )
            return

        raise Exception("Input counter_proposals have been altered or deleted")

    @decorators.action(detail=False, methods=['post'], url_path="update_proposal_indexes")
    def update_proposal_indexes(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        positive_proposal_indexes = data.get('positive_proposal_indexes', None)
        negative_proposal_indexes = data.get('negative_proposal_indexes', None)
        poll = data.get('poll', None)
        if poll and isinstance(positive_proposal_indexes, list) and isinstance(negative_proposal_indexes, list):
            poll = Poll.objects.filter(id=poll).first()
            group = Group.objects.filter(Q(owners__in=[user]) | Q(admins__in=[user]) |
                                         Q(moderators__in=[user]) | Q(members__in=[user]) |
                                         Q(delegators__in=[user]), id=poll.group_id).first()
            if poll:
                if group:
                    delegator = PollUserDelegate.objects.filter(user=user, group=poll.group).first()
                    if not delegator:
                        self.__update_proposal_indexes(user, poll, positive_proposal_indexes, negative_proposal_indexes)
                        result = success_response(data=None, message="Counter proposal index updated successfully.")
                        return Ok(result)
                    return BadRequest(failed_response(data="", message="User cannot vote when votes is already"
                                                                       " delegated"))
                return BadRequest(failed_response(data="", message="User is not in group related to the poll"))
            return BadRequest(failed_response(data="", message="Invalid Poll ID"))
        return BadRequest(failed_response(data="", message="Missing arguments"))

    @decorators.action(detail=False, methods=['post'], url_path="delete_counter_proposal")
    def delete_counter_proposal(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        proposal = data.get('proposal', None)
        if proposal:
            # get counter proposal of poll
            proposal = PollCounterProposal.objects.filter(id=proposal)
            if proposal:
                # check the permission of user to access the proposal
                proposal = proposal.filter(Q(user=user) | Q(poll__group__owners__in=[user]) | Q(poll__group__admins__in=[user]) | Q(poll__group__moderators__in=[user]))
                if proposal:  # if proposal exist then delete that proposal
                    proposal.delete()
                    result = success_response(data=None, message="Proposal data deleted successfully.")
                    return Created(result)
                result = failed_response(data=None, message="Proposal does not exist.")
                return BadRequest(result)
            result = failed_response(data=None, message="Proposal does not exist.")
            return BadRequest(result)
        result = failed_response(data=None, message="Please pass poll parameter with poll id.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="create_counter_proposal_comment")
    def create_counter_proposal_comment(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        # get counter proposal of poll by id
        counter_proposal = PollCounterProposal.objects.filter(id=data.get('counter_proposal'))
        if counter_proposal:
            # check the user permission
            counter_proposal = counter_proposal.filter(Q(user=user),  Q(poll__group__owners__in=[user]) | Q(poll__group__admins__in=[user]) | Q(poll__group__moderators__in=[user]) |
                                                       Q(poll__group__members__in=[user]))
            if counter_proposal:
                # serializer for create counter proposal comment
                serializer = CreateCounterProposalCommentSerializer(data=data)
                if serializer.is_valid():
                    comment = PollCounterProposalComments.objects.create(comment=serializer.validated_data.get('comment'),
                                                                         counter_proposal=serializer.validated_data.get('counter_proposal'),
                                                                         reply_to=serializer.validated_data.get('reply_to'),
                                                                         created_by=user, modified_by=user)
                    comment.save()
                    serializer = GetPollCounterProposalDetailsSerializer(comment.counter_proposal, context={'request': self.request})
                    result = success_response(data=serializer.data, message="Create counter proposal comment successfully.")
                    return Created(result)
                result = failed_response(data=serializer.errors, message="")
                return BadRequest(result)
            result = failed_response(data=None, message="You don't have permission to add comment in this proposal.")
            return BadRequest(result)
        result = failed_response(data=None, message="Counter proposal does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="edit_counter_proposal_comment")
    def edit_counter_proposal_comment(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        # get counter proposal comment of poll id
        counter_proposal_comment = PollCounterProposalComments.objects.filter(id=data.get('comment_id')).first()
        if counter_proposal_comment:
            group = counter_proposal_comment.counter_proposal.poll.group
            # check the user permission and edit the comment
            if counter_proposal_comment.created_by == user or user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():
                counter_proposal_comment.comment = data.get('comment')
                counter_proposal_comment.modified_by = user
                counter_proposal_comment.edited = True
                counter_proposal_comment.save()

                serializer = GetPollCounterProposalDetailsSerializer(counter_proposal_comment.counter_proposal, context={'request': self.request})
                result = success_response(data=serializer.data, message="Counter proposal comment edited successfully.")
                return Created(result)
            result = failed_response(data=None, message="Only comment creator, owner of group, admins or moderators"
                                                        "can edit the comment")
            return BadRequest(result)
        result = failed_response(data=None, message="Counter proposal comment does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="delete_counter_proposal_comment")
    def delete_counter_proposal_comment(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        # get counter proposal comment of poll by id
        comment = PollCounterProposalComments.objects.filter(id=data.get('comment')).first()
        if comment:
            counter_proposal = comment.counter_proposal
            group = counter_proposal.poll.group
            # check user permission and delete comment
            if comment.created_by == user or user in group.owners.all() or user in group.admins.all() or user in group.moderators.all():
                comment.delete()
                serializer = GetPollCounterProposalDetailsSerializer(counter_proposal, context={'request': self.request})
                result = success_response(data=serializer.data, message="Counter Proposal comment deleted successfully.")
                return Created(result)

            result = failed_response(data=None, message="Only comment creator, owner of group, admins or moderator can "
                                                        "delete the comment")
            return BadRequest(result)
        result = failed_response(data=None, message="Counter proposal comment does not exist.")
        return BadRequest(result)

    @decorators.action(detail=False, methods=['post'], url_path="like_dislike_counter_proposal_comment")
    def like_dislike_counter_proposal_comment(self, request, *args, **kwargs):
        user = request.user
        data = request.data
        like = data.get('like', None)
        # get counter proposal comment of poll by id
        counter_proposal_comment = PollCounterProposalComments.objects.filter(id=data.get('counter_proposal_comment')).first()
        if counter_proposal_comment:
            # if already liked then remove the like otherwise like that comment
            if like:
                counter_proposal_comment.likes.add(user)
                counter_proposal_comment.save()
            else:
                counter_proposal_comment.likes.remove(user)
                counter_proposal_comment.save()
            serializer = GetPollCounterProposalDetailsSerializer(counter_proposal_comment.counter_proposal, context={'request': self.request})
            result = success_response(data=serializer.data, message="Comment deleted successfully.")
            return Created(result)
        result = failed_response(data=None, message="Comment does not exist.")
        return BadRequest(result)