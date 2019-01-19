from flask import abort, current_app, flash, redirect, request, url_for
from flask_allows import requires, Or
from flask_restful import Resource, reqparse
from flask_login import current_user
from webargs.flaskparser import use_args
from opsy.access import (HasPermission, is_logged_in, is_same_user,
                         users_create, users_read, users_update, users_delete,
                         roles_create, roles_read, roles_update, roles_delete)
from opsy.auth import login, logout, create_token
from opsy.schema import (UserSchema, UserLoginSchema, UserTokenSchema,
                         UserSettingSchema, RoleSchema)
from opsy.models import User, Role
from opsy.exceptions import DuplicateError


class Login(Resource):

    @requires(is_logged_in)
    def get(self):  # pylint: disable=no-self-use
        create_token(current_user)
        return UserTokenSchema().jsonify(current_user)

    @use_args(UserLoginSchema(), locations=('form', 'json'))
    def post(self, args):  # pylint: disable=inconsistent-return-statements
        current_app.logger.info(args)
        user = login(args['user_name'], args['password'],
                     remember=args['remember_me'])
        if not user:
            if request.is_json:
                abort(401, 'Username or password incorrect.')
            else:
                flash('Username or password incorrect.')
                return redirect(url_for('core_main.about'))
        if request.is_json:
            return UserTokenSchema().jsonify(current_user)
        return redirect(url_for('core_main.about'))


class Logout(Resource):

    @requires(is_logged_in)
    def get(self):  # pylint: disable=no-self-use
        logout(current_user)
        return redirect(url_for('core_main.about'))


class RolesAPI(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('name')
        self.reqparse.add_argument('ldap_group')
        self.reqparse.add_argument('description')
        super().__init__()

    @requires(HasPermission(roles_create))
    def post(self):
        self.reqparse.replace_argument('name', required=True)
        args = self.reqparse.parse_args()
        try:
            role = Role.create(**args)
        except (DuplicateError, ValueError) as error:
            abort(400, str(error))
        return RoleSchema().jsonify(role)

    @requires(HasPermission(roles_read))
    def get(self):
        args = self.reqparse.parse_args()
        roles = Role.query.wtfilter_by(prune_none_values=True, **args)
        return RoleSchema(many=True).jsonify(roles)


class RoleAPI(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        super().__init__()

    @requires(HasPermission(roles_read))
    def get(self, role_name):  # pylint: disable=no-self-use
        role = Role.query.wtfilter_by(name=role_name).first()
        if not role:
            abort(403)
        return RoleSchema().jsonify(role)

    @requires(HasPermission(roles_update))
    def patch(self, role_name):
        self.reqparse.add_argument('name')
        self.reqparse.add_argument('ldap_group')
        self.reqparse.add_argument('description')
        args = self.reqparse.parse_args()
        role = Role.query.wtfilter_by(name=role_name).first()
        if not role:
            abort(404)
        role.update(prune_none_values=True, **args)
        return RoleSchema().jsonify(role)

    @requires(HasPermission(roles_delete))
    def delete(self, role_name):  # pylint: disable=no-self-use
        role = Role.query.wtfilter_by(name=role_name).first()
        if not role:
            abort(404)
        role.delete()
        return ('', 202)


class UsersAPI(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('name')
        self.reqparse.add_argument('full_name')
        self.reqparse.add_argument('email')
        self.reqparse.add_argument('enabled')
        super().__init__()

    @requires(HasPermission(users_create))
    def post(self):
        self.reqparse.replace_argument('name', required=True)
        args = self.reqparse.parse_args()
        try:
            user = User.create(**args)
        except (DuplicateError, ValueError) as error:
            abort(400, str(error))
        return UserSchema().jsonify(user)

    @requires(HasPermission(users_read))
    def get(self):
        args = self.reqparse.parse_args()
        users = User.query.wtfilter_by(prune_none_values=True, **args)
        return UserSchema(many=True).jsonify(users)


class UserAPI(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        super().__init__()

    @requires(Or(HasPermission(users_read), is_same_user))
    def get(self, user_name):  # pylint: disable=no-self-use
        user = User.query.wtfilter_by(name=user_name).first()
        if not user:
            abort(403)
        return UserSchema().jsonify(user)

    @requires(Or(HasPermission(users_update), is_same_user))
    def patch(self, user_name):
        self.reqparse.add_argument('full_name')
        self.reqparse.add_argument('email')
        self.reqparse.add_argument('enabled')
        args = self.reqparse.parse_args()
        user = User.query.wtfilter_by(name=user_name).first()
        if not user:
            abort(404)
        user.update(prune_none_values=True, **args)
        return UserSchema().jsonify(user)

    @requires(HasPermission(users_delete))
    def delete(self, user_name):  # pylint: disable=no-self-use
        user = User.query.wtfilter_by(name=user_name).first()
        if not user:
            abort(404)
        user.delete()
        return ('', 202)


class UserSettingsAPI(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('key')
        self.reqparse.add_argument('value')
        super().__init__()

    @requires(Or(HasPermission(users_update), is_same_user))
    def post(self, user_name):
        self.reqparse.replace_argument('key', required=True)
        self.reqparse.replace_argument('value', required=True)
        args = self.reqparse.parse_args()
        user = User.query.wtfilter_by(name=user_name).first()
        if not user:
            abort(404)
        try:
            setting = user.add_setting(args['key'], args['value'])
        except DuplicateError as error:
            abort(400, str(error))
        return UserSettingSchema().jsonify(setting)

    @requires(Or(HasPermission(users_read), is_same_user))
    def get(self, user_name):
        user = User.query.wtfilter_by(name=user_name).first()
        if not user:
            abort(404)
        return UserSettingSchema(many=True).jsonify(user.settings)


class UserSettingAPI(Resource):

    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('value', required=True, location='json')
        super().__init__()

    @requires(Or(HasPermission(users_update), is_same_user))
    def patch(self, user_name, setting_key):
        args = self.reqparse.parse_args()
        user = User.query.wtfilter_by(name=user_name).first()
        if not user:
            abort(404)
        try:
            setting = user.modify_setting(setting_key, args['value'])
        except ValueError as error:
            abort(404, str(error))
        return UserSettingSchema().jsonify(setting)

    @requires(Or(HasPermission(users_read), is_same_user))
    def get(self, user_name, setting_key):
        user = User.query.wtfilter_by(name=user_name).first()
        if not user:
            abort(404)
        try:
            setting = user.get_setting(setting_key, error_on_none=True)
        except ValueError as error:
            abort(404, str(error))
        return UserSettingSchema().jsonify(setting)

    @requires(Or(HasPermission(users_update), is_same_user))
    def delete(self, user_name, setting_key):
        user = User.query.wtfilter_by(name=user_name).first()
        if not user:
            abort(404)
        try:
            user.remove_setting(setting_key)
        except ValueError as error:
            abort(404, str(error))
        return ('', 202)